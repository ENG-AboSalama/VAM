"""
VAM - Valorant Account Manager
Configuration & Settings

Developer: NIR0
Powered By: CursedTools
"""

import os

# ─── App Info ────────────────────────────────────────────────
APP_NAME = "VAM"
APP_FULL_NAME = "Valorant Account Manager"
APP_VERSION = "1.7.9"
APP_DEVELOPER = "NIR0"
APP_POWERED_BY = "CursedTools"

# ─── Game Constants ──────────────────────────────────────────
RANKED_READY_LEVEL = 20
DOUBLE_GAME_LEVEL = 15          # After level 15, FWOTD needs 2 wins
FWOTD_COOLDOWN_HOURS = 22       # First Win of the Day resets every 22h

# ─── HenrikDev API ───────────────────────────────────────────
HENRIK_API_BASE_URL = "https://api.henrikdev.xyz/valorant"
HENRIK_API_KEY = "HDEV-e8c5cedd-2cf8-4308-8ac2-2665bc223ca3"
HENRIK_API_RATE_LIMIT = 30      # requests per minute (Basic plan)
HENRIK_API_RATE_WINDOW = 60     # seconds

# ─── Paths ───────────────────────────────────────────────────
# Default Riot Client installation path
RIOT_CLIENT_DEFAULT_PATH = r"C:\Riot Games\Riot Client"
RIOT_CLIENT_EXE = "RiotClientServices.exe"
RIOT_CLIENT_LAUNCH_ARGS = ["--launch-product=valorant", "--launch-patchline=live"]

# Main Valorant game process (used for detecting game running/closed)
VALORANT_GAME_PROCESS = "VALORANT-Win64-Shipping.exe"

# Riot lockfile path
RIOT_LOCKFILE_PATH = os.path.join(
    os.getenv("LOCALAPPDATA", ""),
    "Riot Games", "Riot Client", "Config", "lockfile"
)

# Riot Client Data directory (for session files)
RIOT_CLIENT_DATA_PATH = os.path.join(
    os.getenv("LOCALAPPDATA", ""),
    "Riot Games", "Riot Client", "Data"
)

# VAM data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
CONFIG_FILE = os.path.join(DATA_DIR, "app_config.json")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
PROOFS_DIR = os.path.join(DATA_DIR, "proofs")

# ─── Take Proofs Settings ────────────────────────────────────
VALORANT_LOAD_DELAY = 65       # Seconds to wait for Valorant main menu to fully load
PLAY_BUTTON_CLICK_DELAY = 2     # Seconds to wait after clicking PLAY for queue screen

# ─── Riot Processes ──────────────────────────────────────────
# Processes to kill before auto-login (DO NOT include Vanguard - it must stay running)
RIOT_CLIENT_PROCESSES = [
    "RiotClientServices.exe",
    "RiotClientUx.exe",
    "RiotClientUxRender.exe",
    "RiotClientCrashHandler.exe",
]

VALORANT_PROCESSES = [
    "VALORANT.exe",
    "VALORANT-Win64-Shipping.exe",
]

# Vanguard processes - NEVER kill these, Riot Client depends on them
VANGUARD_PROCESSES = [
    "vgc.exe",
    "vgtray.exe",
]

# Combined list for detection only (not killing)
ALL_RIOT_PROCESS_NAMES = RIOT_CLIENT_PROCESSES + VALORANT_PROCESSES + VANGUARD_PROCESSES

# Processes safe to kill for account switching
KILLABLE_RIOT_PROCESSES = RIOT_CLIENT_PROCESSES + VALORANT_PROCESSES

# ─── UI Theme Colors (Valorant-inspired) ────────────────────
COLORS = {
    "primary": "#FF4655",       # Valorant Red
    "secondary": "#0F1923",     # Dark Background
    "accent": "#BD3944",        # Dark Red
    "success": "#2ECC71",       # Green
    "warning": "#F39C12",       # Orange/Yellow
    "error": "#E74C3C",         # Red
    "info": "#3498DB",          # Blue
    "text": "#ECE8E1",          # Light text
    "muted": "#768079",         # Muted gray-green
    "highlight": "#FF4655",     # Highlight red
    "level_low": "#E74C3C",     # Level 1-5
    "level_mid": "#F39C12",     # Level 6-14
    "level_high": "#2ECC71",    # Level 15-19
    "level_ready": "#00FFFF",   # Level 20 (Ranked Ready)
}

# ─── Account Statuses ───────────────────────────────────────
class AccountStatus:
    NEW = "new"                         # Just added, no data fetched
    IN_PROGRESS = "in_progress"         # Being leveled
    RANKED_READY = "ranked_ready"       # Level 20, ready to sell
    ERROR = "error"                     # API error or issue


def ensure_data_dirs():
    """Create data directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(PROOFS_DIR, exist_ok=True)
