"""
VAM - Riot Client Service
Auto-login via GUI automation and Riot Client management.

Approach:
- Window detection via Win32 EnumWindows with size filtering
- Win32 Clipboard API (ctypes) for pasting — no PowerShell dependency
- Keyboard-only navigation: Tab to fields, Ctrl+V to paste
- AttachThreadInput + Alt trick to force reliable window focus
- Click inside window to activate CEF/Chromium browser content
"""

import os
import time
import subprocess
import ctypes
import ctypes.wintypes
import psutil
import pyautogui
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from config.settings import (
    RIOT_CLIENT_DEFAULT_PATH, RIOT_CLIENT_EXE,
    RIOT_CLIENT_LAUNCH_ARGS, KILLABLE_RIOT_PROCESSES,
    RIOT_LOCKFILE_PATH, VALORANT_GAME_PROCESS,
    VALORANT_PROCESSES,
)
from ui.console import console, print_status
from services.riot_session_manager import RiotSessionManager


# Configure pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# Minimum window size to be considered a real login window
MIN_WINDOW_WIDTH = 400
MIN_WINDOW_HEIGHT = 300


# ─── Win32 Clipboard API ────────────────────────────────────
def _clipboard_set(text: str) -> bool:
    """
    Set clipboard text using Win32 API directly.
    Retries OpenClipboard up to 20 times (another process may have it locked).
    Returns True on success, False on failure.

    IMPORTANT: restype must be set to c_void_p for GlobalAlloc/GlobalLock,
    otherwise ctypes truncates 64-bit handles to 32-bit int on x64 systems.
    """
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    # --- Fix 64-bit pointer truncation ---
    # Without this, ctypes defaults restype to c_int (32-bit),
    # which silently truncates 64-bit memory handles → GlobalLock fails.
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    # Encode text as UTF-16-LE with null terminator
    encoded = text.encode("utf-16-le") + b"\x00\x00"
    byte_count = len(encoded)

    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, byte_count)
    if not h_mem:
        print_status("GlobalAlloc failed!", "error")
        return False

    p_mem = kernel32.GlobalLock(h_mem)
    if not p_mem:
        print_status("GlobalLock failed!", "error")
        kernel32.GlobalFree(h_mem)
        return False

    # Use ctypes.memmove (safe, no temp objects, works on all architectures)
    ctypes.memmove(p_mem, encoded, byte_count)
    kernel32.GlobalUnlock(h_mem)

    # Retry opening clipboard — fails if another process (e.g. Discord) has it locked
    opened = False
    for attempt in range(20):
        if user32.OpenClipboard(0):
            opened = True
            break
        time.sleep(0.15)

    if not opened:
        print_status("Could not open clipboard after 20 retries!", "error")
        kernel32.GlobalFree(h_mem)
        return False

    user32.EmptyClipboard()
    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    user32.CloseClipboard()
    return True


def _clipboard_clear():
    """Clear clipboard contents."""
    for _ in range(5):
        if ctypes.windll.user32.OpenClipboard(0):
            ctypes.windll.user32.EmptyClipboard()
            ctypes.windll.user32.CloseClipboard()
            return
        time.sleep(0.1)


# ─── Win32 Keyboard Helpers ─────────────────────────────────
# pyautogui.hotkey("ctrl", "v") is broken for CEF/Chromium apps because
# pyautogui.PAUSE (0.15s) inserts a 150ms gap between Ctrl-down and V-down.
# The app sees "Ctrl pressed alone" instead of "Ctrl+V combo".
# Using keybd_event directly gives us tight timing control.

def _send_ctrl_v():
    """Send Ctrl+V via Win32 keybd_event. Tight timing, no pyautogui.PAUSE."""
    user32 = ctypes.windll.user32
    VK_CONTROL = 0x11
    VK_V = 0x56
    KEYEVENTF_KEYUP = 0x0002

    user32.keybd_event(VK_CONTROL, 0, 0, 0)                 # Ctrl down
    time.sleep(0.05)
    user32.keybd_event(VK_V, 0, 0, 0)                       # V down
    time.sleep(0.05)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)         # V up
    time.sleep(0.05)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)   # Ctrl up


def _send_ctrl_a():
    """Send Ctrl+A via Win32 keybd_event. Tight timing, no pyautogui.PAUSE."""
    user32 = ctypes.windll.user32
    VK_CONTROL = 0x11
    VK_A = 0x41
    KEYEVENTF_KEYUP = 0x0002

    user32.keybd_event(VK_CONTROL, 0, 0, 0)                 # Ctrl down
    time.sleep(0.05)
    user32.keybd_event(VK_A, 0, 0, 0)                       # A down
    time.sleep(0.05)
    user32.keybd_event(VK_A, 0, KEYEVENTF_KEYUP, 0)         # A up
    time.sleep(0.05)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)   # Ctrl up


# ─── Window Detection ───────────────────────────────────────
class WindowInfo:
    """Stores info about a detected window."""
    def __init__(self, hwnd, title, left, top, width, height):
        self.hwnd = hwnd
        self.title = title
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.right = left + width
        self.bottom = top + height
        self.center_x = left + width // 2
        self.center_y = top + height // 2


def _find_riot_login_window() -> WindowInfo | None:
    """
    Find the Riot Client LOGIN window.
    Filters by title ("Riot Client") and minimum size.
    Saves geometry at detection time to avoid stale HWND issues.
    """
    candidates = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_callback(hwnd, lparam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True

        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        if "riot client" not in title.lower():
            return True

        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        if w >= MIN_WINDOW_WIDTH and h >= MIN_WINDOW_HEIGHT:
            candidates.append(WindowInfo(hwnd, title, rect.left, rect.top, w, h))

        return True

    ctypes.windll.user32.EnumWindows(enum_callback, 0)

    if candidates:
        # Pick the largest window
        candidates.sort(key=lambda c: c.width * c.height, reverse=True)
        win = candidates[0]
        print_status(
            f"Found: '{win.title}' ({win.width}x{win.height}) at ({win.left}, {win.top})",
            "info",
        )
        return win

    return None


def _force_foreground(hwnd: int):
    """
    Force a window to the foreground reliably.

    SetForegroundWindow alone fails silently on Windows because the OS
    blocks focus-stealing. We work around this by:
    1. AttachThreadInput — link our thread's input queue to the foreground
       window's thread so the OS treats us as the active input context.
    2. Alt key trick — pressing Alt satisfies the OS requirement that the
       calling process received the last input event.
    3. Then SetForegroundWindow + BringWindowToTop.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    try:
        # Restore if minimized
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            time.sleep(0.5)

        # Get thread IDs
        our_thread = kernel32.GetCurrentThreadId()
        fg_hwnd = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

        # Attach our thread input to the current foreground thread
        attached = False
        if fg_thread and fg_thread != our_thread:
            attached = bool(user32.AttachThreadInput(our_thread, fg_thread, True))

        # Press Alt to satisfy the "last input" requirement
        user32.keybd_event(0x12, 0, 0, 0)       # VK_MENU (Alt) down
        user32.keybd_event(0x12, 0, 0x0002, 0)   # VK_MENU (Alt) up  (KEYEVENTF_KEYUP)

        # Now SetForegroundWindow should succeed
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        
        # Force window to be physically on top of everything (including Always On Top terminals)
        # HWND_TOPMOST = -1, SWP_NOMOVE = 2, SWP_NOSIZE = 1
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 3)
        time.sleep(0.1)
        # Restore normal Z-order but keep it on top (HWND_NOTOPMOST = -2)
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 3)
        
        user32.SetFocus(hwnd)

        # Detach
        if attached:
            user32.AttachThreadInput(our_thread, fg_thread, False)

    except Exception:
        # Fallback: at least try the basic call
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass


def _click_window_center(win):
    """
    Click the center of a window to give the CEF/Chromium browser
    content keyboard focus. Without this, keyboard events go nowhere
    because the Win32 window has focus but the embedded browser does not.
    """
    screen_w, screen_h = pyautogui.size()
    cx = max(10, min(win.center_x, screen_w - 10))
    cy = max(10, min(win.center_y, screen_h - 10))
    pyautogui.click(cx, cy)


# ─── Main Class ─────────────────────────────────────────────
class RiotClient:
    """Manages Riot Client interactions: process control, auto-login, game launch."""

    def __init__(self, riot_client_path: str = "", valorant_path: str = ""):
        self.riot_path = riot_client_path or self._detect_riot_path()
        self.exe_path = os.path.join(self.riot_path, RIOT_CLIENT_EXE) if self.riot_path else ""
        self.valorant_path = valorant_path
        self.session_mgr = RiotSessionManager()

    @staticmethod
    def _detect_riot_path() -> str:
        """Auto-detect Riot Client installation path."""
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game riot_client.live")
            path, _ = winreg.QueryValueEx(key, "InstallLocation")
            if path and os.path.exists(os.path.join(path, RIOT_CLIENT_EXE)):
                return path
        except (FileNotFoundError, OSError):
            pass

        candidates = [
            RIOT_CLIENT_DEFAULT_PATH,
            r"C:\Riot Games\Riot Client",
            r"D:\Riot Games\Riot Client",
            r"E:\Riot Games\Riot Client",
            os.path.join(os.getenv("PROGRAMFILES", ""), "Riot Games", "Riot Client"),
            os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Riot Games", "Riot Client"),
        ]
        for path in candidates:
            if os.path.exists(os.path.join(path, RIOT_CLIENT_EXE)):
                return path
        return ""

    def is_valid(self) -> bool:
        return bool(self.exe_path) and os.path.exists(self.exe_path)

    def is_running(self) -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] in KILLABLE_RIOT_PROCESSES:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def kill_riot_processes(self) -> bool:
        """Kill Riot Client + Valorant processes. NEVER kills Vanguard."""
        killed = False
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if proc.info["name"] in KILLABLE_RIOT_PROCESSES:
                    print_status(f"Killing {proc.info['name']} (PID: {proc.info['pid']})...", "wait")
                    proc.terminate()
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if killed:
            time.sleep(3)
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    if proc.info["name"] in KILLABLE_RIOT_PROCESSES:
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            time.sleep(2)

        return True

    def launch_client(self, launch_game: bool = False) -> bool:
        """Launch the Riot Client. If launch_game=True, includes Valorant product flags."""
        if not self.is_valid():
            print_status("Riot Client not found. Check your path in settings.", "error")
            return False
        try:
            args = [self.exe_path]
            if launch_game:
                args += RIOT_CLIENT_LAUNCH_ARGS
            subprocess.Popen(
                args,
                cwd=self.riot_path,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            print_status("Riot Client launched.", "success")
            return True
        except OSError as e:
            print_status(f"Failed to launch: {e}", "error")
            return False

    @staticmethod
    def _detect_valorant_path() -> str:
        """Auto-detect Valorant installation path using Riot's metadata."""
        try:
            metadata_path = r"C:\ProgramData\Riot Games\Metadata\valorant.live\valorant.live.product_settings.yaml"
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "product_install_full_path" in line:
                            path = line.split('"')[1]
                            exe_path = os.path.join(path, "VALORANT.exe")
                            if os.path.exists(exe_path):
                                return exe_path
        except Exception:
            pass
            
        # Fallbacks
        candidates = [
            r"C:\Riot Games\VALORANT\live\VALORANT.exe",
            r"D:\Riot Games\VALORANT\live\VALORANT.exe",
            r"E:\Riot Games\VALORANT\live\VALORANT.exe",
            r"F:\Riot Games\VALORANT\live\VALORANT.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return ""

    def launch_valorant_directly(self) -> bool:
        """Launch Valorant directly. Handles Access Denied by using Riot URI scheme."""
        val_path = self.valorant_path or self._detect_valorant_path()
        
        # Try direct executable launch
        if val_path and os.path.exists(val_path):
            try:
                os.startfile(val_path)
                print_status(f"Started {val_path}", "success")
                return True
            except OSError as e:
                # If we get WinError 5 (Access Denied), fallback to the URI scheme below
                pass
        
        # Fallback to official Riot Client URI scheme
        print_status("Using Riot URI scheme to launch game...", "info")
        try:
            os.startfile("riotclient://launch-product=valorant&launch-patchline=live")
            return True
        except OSError as e:
            print_status(f"Failed to launch via URI scheme: {e}", "error")
            
        return False

    def _click_play_button(self, win) -> None:
        """Click the big red Play button on the Riot Client home screen."""
        if not win:
            return
        
        # The 'Play' button is located at roughly 20% width and 33% height of the client window
        play_x = win.left + int(win.width * 0.20)
        play_y = win.top + int(win.height * 0.33)
        
        print_status(f"Clicking Play button at ({play_x}, {play_y})...", "wait")
        
        # Force foreground just in case
        _force_foreground(win.hwnd)
        time.sleep(0.5)
        
        # Move smoothly and click
        pyautogui.moveTo(play_x, play_y, duration=0.2)
        pyautogui.click()
        time.sleep(0.5)

    def wait_for_riot_window(self, timeout: int = 60) -> WindowInfo | None:
        """Wait for the Riot Client login window. Returns WindowInfo with saved geometry."""
        print_status("Waiting for Riot Client window...", "wait")
        start = time.time()

        while time.time() - start < timeout:
            win = _find_riot_login_window()
            if win:
                print_status("Window detected! Waiting for UI to fully load...", "success")
                time.sleep(5)

                # Re-detect to get final position (window might move during load)
                win2 = _find_riot_login_window()
                if win2:
                    return win2
                return win

            time.sleep(1)

        return None

    def auto_login(self, username: str, password: str, launch_game: bool = False) -> tuple[bool, dict]:
        """
        Full auto-login via keyboard navigation:
        1. Kill Riot processes (not Vanguard)
        2. Launch Riot Client (with/without Valorant game launch)
        3. Detect login window
        4. Force-focus window + click center (activate CEF browser content)
        5. Tab x3 → navigate to username field → Ctrl+V paste username
        6. Tab x1 → navigate to password field → Ctrl+V paste password
        7. Tab x7 → navigate to Login button → Enter
        
        Args:
            launch_game: If True, launches Valorant after login. If False, only opens Riot Client.
        """
        console.print()

        # Step 1: Kill processes
        print_status("Closing existing Riot Client processes...", "wait")
        self.kill_riot_processes()
        
        # Step 1.5: Wipe existing session to force login screen
        print_status("Clearing existing session...", "wait")
        self.session_mgr.clear_session()

        # Step 2: Launch
        print_status("Launching Riot Client...", "wait")
        if not self.launch_client(launch_game=launch_game):
            return False, {}

        # Step 3: Wait for window
        win = self.wait_for_riot_window(timeout=60)
        if not win:
            print_status("Timeout waiting for Riot Client window.", "error")
            return False, {}

        print_status(
            f"Window: ({win.left},{win.top}) size {win.width}x{win.height}",
            "info",
        )

        # Step 4: Force-focus the window
        print_status("Focusing window...", "wait")
        _force_foreground(win.hwnd)
        time.sleep(0.5)

        # Click the CENTER of the window — this is CRITICAL.
        # The Riot Client is a CEF/Chromium app. SetForegroundWindow gives
        # Win32 focus to the outer frame, but the embedded browser control
        # won't receive keyboard input until you physically click inside it.
        # print_status("Activating browser content (click)...", "wait")
        # _click_window_center(win)
        # time.sleep(0.1)

        # Step 5: Keyboard-only login form interaction
        # NOTE: We use _send_ctrl_v() / _send_ctrl_a() instead of
        # pyautogui.hotkey() because pyautogui.PAUSE adds 150ms between
        # Ctrl-down and V-down, which CEF apps don't recognize as Ctrl+V.
        try:
            # --- Navigate to USERNAME field (3 Tabs) ---
            # print_status("Navigating to username field (3x Tab)...", "wait")
            # for i in range(3):
            #     pyautogui.press("tab")
            #     time.sleep(0.1)
            # time.sleep(0.1)

            # Select all existing text (if any)
            _send_ctrl_a()
            # time.sleep(0.1)

            # Paste username via clipboard
            print_status("Pasting username...", "wait")
            if not _clipboard_set(username):
                print_status("Failed to set clipboard for username!", "error")
                return False, {}
            time.sleep(0.1)
            _send_ctrl_v()
            time.sleep(0.2)

            # --- Navigate to PASSWORD field (1 Tab) ---
            print_status("Navigating to password field (1x Tab)...", "wait")
            pyautogui.press("tab")
            time.sleep(0.1)

            # Paste password via clipboard
            print_status("Pasting password...", "wait")
            if not _clipboard_set(password):
                print_status("Failed to set clipboard for password!", "error")
                return False, {}
            time.sleep(0.1)
            _send_ctrl_v()
            time.sleep(0.1)

            # Clear clipboard immediately (security)
            _clipboard_clear()

            # --- Navigate to 'Stay signed in' checkbox (6 Tabs) ---
            print_status("Navigating to 'Stay signed in' (6x Tab)...", "wait")
            for i in range(6):
                pyautogui.press("tab")
                time.sleep(0.1)
                
            print_status("Checking 'Stay signed in'...", "wait")
            pyautogui.press("space")
            time.sleep(0.1)

            # --- Navigate to LOGIN button (1 Tab) ---
            print_status("Navigating to login button (1x Tab)...", "wait")
            pyautogui.press("tab")
            time.sleep(0.1)

            # --- Submit ---
            print_status("Pressing Enter...", "wait")
            pyautogui.press("enter")

            print_status("Login submitted! Waiting for authentication...", "success")
            time.sleep(5)
            
            # Verify login succeeded via local API
            if self.verify_session(timeout=10):
                print_status("Login verified!", "success")
            else:
                print_status("Login verification failed.", "warning")
                return False, {}
            
            if launch_game:
                print_status("Triggering Valorant launch...", "wait")
                launched = self.launch_valorant_directly()
                
                if not launched:
                    # Fallback: click the Play button on Riot Client
                    print_status("Clicking Play button on Riot Client...", "wait")
                    self._click_play_button(win)
            
            # Extract cookies after verified login
            print_status("Extracting session cookies...", "wait")
            cookies = {}
            for _ in range(15):
                time.sleep(1)
                cookies = self.session_mgr.extract_cookies()
                if "ssid" in cookies:
                    break
                    
            if cookies and "ssid" in cookies:
                print_status("Session cookies extracted successfully!", "success")
                return True, cookies
            else:
                print_status("Could not extract session cookies (ssid missing).", "warning")
                return False, cookies

        except Exception as e:
            _clipboard_clear()
            print_status(f"Auto-login error: {e}", "error")
            return False, {}
            
    def verify_session(self, timeout: int = 15) -> bool:
        """Check if the client is successfully logged in via the local API."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            lockfile = self.read_lockfile()
            if lockfile:
                port = lockfile["port"]
                password = lockfile["password"]
                url = f"https://127.0.0.1:{port}/riot-client-auth/v1/userinfo"
                try:
                    response = requests.get(url, auth=("riot", password), verify=False, timeout=3)
                    if response.status_code == 200:
                        return True
                except requests.exceptions.RequestException:
                    pass
            time.sleep(1)
            
        return False

    def silent_login(self, cookies: dict, launch_game: bool = False) -> bool:
        """
        Injects cookies and launches the client/game silently without UI automation.
        """
        if not cookies or "ssid" not in cookies:
            print_status("No valid full session (missing ssid) provided for silent login.", "error")
            return False
            
        print_status("Closing existing Riot Client processes...", "wait")
        self.kill_riot_processes()
        
        print_status("Wiping old session data...", "wait")
        self.session_mgr.clear_session()
        
        print_status("Injecting session cookies...", "wait")
        if not self.session_mgr.inject_cookies(cookies):
            print_status("Failed to inject cookies into Riot settings.", "error")
            return False
            
        print_status("Launching Riot Client silently...", "wait")
        if not self.launch_client(launch_game=launch_game):
            return False
            
        print_status("Verifying session validity...", "wait")
        if not self.verify_session(timeout=10):
            print_status("Session rejected (likely expired).", "warning")
            return False
            
        if launch_game:
            time.sleep(2)
            print_status("Triggering Valorant launch...", "wait")
            self.launch_valorant_directly()
            
        return True

    def click_valorant_play_button(self) -> bool:
        """
        Click the PLAY button on the Valorant main screen.
        The PLAY button is at the top-center of the screen.
        Based on the screenshot: ~50% width, ~4% height from top.
        """
        screen_w, screen_h = pyautogui.size()
        play_x = int(screen_w * 0.50)
        play_y = int(screen_h * 0.04)
        
        print_status(f"Clicking PLAY button at ({play_x}, {play_y})...", "wait")
        pyautogui.moveTo(play_x, play_y, duration=0.2)
        pyautogui.click()
        return True
        
    def take_screenshot(self, save_path: str) -> bool:
        """Take a full-screen screenshot and save it."""
        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(save_path)
            return True
        except Exception as e:
            print_status(f"Failed to take screenshot: {e}", "error")
            return False

    def is_valorant_running(self) -> bool:
        """Check if the Valorant game process is currently running."""
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] in VALORANT_PROCESSES:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def wait_for_valorant_launch(self, timeout: int = 180) -> bool:
        """
        Wait until the Valorant game process appears.
        Returns True if game launched, False if timed out.
        """
        print_status("Waiting for Valorant to launch...", "wait")
        start = time.time()
        while time.time() - start < timeout:
            if self.is_valorant_running():
                print_status("Valorant is running!", "success")
                return True
            time.sleep(3)
        print_status("Timeout waiting for Valorant to launch.", "error")
        return False

    def wait_for_valorant_close(self, poll_interval: int = 5) -> bool:
        """
        Wait until the Valorant game process disappears (player closed the game).
        Blocks indefinitely until Valorant closes or KeyboardInterrupt.
        Returns True when closed.
        """
        print_status("Waiting for Valorant to close...", "wait")
        while True:
            if not self.is_valorant_running():
                print_status("Valorant has been closed.", "success")
                return True
            time.sleep(poll_interval)

    def kill_valorant(self) -> bool:
        """Kill only Valorant game processes (not Riot Client)."""
        killed = False
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if proc.info["name"] in VALORANT_PROCESSES:
                    print_status(f"Killing {proc.info['name']} (PID: {proc.info['pid']})...", "wait")
                    proc.terminate()
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if killed:
            time.sleep(3)
        return killed

    def read_lockfile(self) -> dict | None:
        """Read the Riot Client lockfile."""
        if not os.path.exists(RIOT_LOCKFILE_PATH):
            return None
        try:
            with open(RIOT_LOCKFILE_PATH, "r") as f:
                data = f.read().strip().split(":")
                if len(data) >= 5:
                    return {
                        "name": data[0],
                        "pid": data[1],
                        "port": data[2],
                        "password": data[3],
                        "protocol": data[4],
                    }
        except IOError:
            pass
        return None
