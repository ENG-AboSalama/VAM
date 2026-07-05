"""
╔══════════════════════════════════════════════════════════════╗
║                VAM - Valorant Account Manager                ║
║                                                              ║
║  Developer:  NIR0                                            ║
║  Powered By: CursedTools                                     ║
║  Version:    1.0.0                                           ║
║                                                              ║
║  A tool to manage Valorant accounts, track FWOTD progress,   ║
║  auto-login, and monitor leveling to Ranked Ready (Lv.20).   ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os
import logging

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'data', 'vam.log')),
        logging.StreamHandler()  # Also log to console
    ]
)

logger = logging.getLogger(__name__)

from core.data_store import DataStore
from core.account_manager import AccountManager
from core.session_manager import SessionManager
from core.setup_wizard import SetupWizard
from services.henrik_api import HenrikAPI
from services.riot_client import RiotClient
from services.display_name_resolver import DisplayNameResolver
from services.valorant_local_api import ValorantLocalAPI
from ui.console import (
    console, clear_screen, print_header, print_status,
    print_success_panel, print_error_panel, pause,
    prompt_confirm, prompt_input,
)
from ui.menus import (
    show_main_menu, show_account_manager_menu,
    show_auto_login_menu, show_settings_menu, show_fwotd_menu,
)
from ui.tables import build_accounts_table, build_summary_stats, build_suffering_dashboard
from ui.banners import get_section_title
from config.settings import APP_NAME, APP_FULL_NAME, APP_VERSION


class VAMApp:
    """Main application controller."""
    
    def __init__(self):
        self.data_store = DataStore()
        self.account_mgr = AccountManager(self.data_store)
        self.session_mgr = SessionManager(self.data_store)
        self.riot_client = None
        self.henrik_api = None
        self.resolver = None
        self.val_api = None
    
    def _init_services(self):
        """Initialize services with saved configuration."""
        config = self.data_store.load_config()
        
        riot_path = config.get("riot_client_path", "")
        valorant_path = config.get("valorant_path", "")
        self.riot_client = RiotClient(riot_path, valorant_path)
        
        api_key = config.get("api_key", "")
        if api_key:
            self.henrik_api = HenrikAPI(api_key)
        
        if self.riot_client:
            self.resolver = DisplayNameResolver(self.riot_client)
            self.val_api = ValorantLocalAPI(self.riot_client)
    
    def run(self):
        """Main application entry point."""
        try:
            # Check for first-run setup
            if not self.data_store.is_setup_complete():
                wizard = SetupWizard(self.data_store)
                if not wizard.run():
                    console.print("\n  [muted]Setup incomplete. Exiting...[/muted]")
                    return
            
            # Initialize services
            self._init_services()
            
            # Main loop
            self._main_loop()
        
        except KeyboardInterrupt:
            console.print("\n\n  [muted]Goodbye! 👋[/muted]\n")
        except Exception as e:
            print_error_panel("Fatal Error", str(e))
            import traceback
            console.print(f"[muted]{traceback.format_exc()}[/muted]")
            pause()
    
    def _main_loop(self):
        """Main menu loop."""
        while True:
            clear_screen()
            
            # Show summary at top
            accounts = self.data_store.load_accounts()
            if accounts:
                console.print(build_summary_stats(accounts))
            
            choice = show_main_menu()
            
            if choice == "1":
                self._account_manager_loop()
            elif choice == "2":
                self._auto_login()
            elif choice == "3":
                self._refresh_data()
            elif choice == "4":
                self._mark_fwotd()
            elif choice == "5":
                self._settings_loop()
            elif choice == "6":
                self._start_suffering()
            elif choice == "7":
                self._take_proofs()
            elif choice == "0":
                console.print("\n  [muted]Goodbye! See you next time. 👋[/muted]\n")
                break
            else:
                print_status("Invalid option.", "error")
                pause()
    
    def _account_manager_loop(self):
        """Account manager submenu loop."""
        while True:
            clear_screen()
            print_header()
            
            choice = show_account_manager_menu()
            
            if choice == "1":
                clear_screen()
                print_header()
                self.account_mgr.view_all_accounts()
            elif choice == "2":
                clear_screen()
                print_header()
                self.account_mgr.add_account_manual()
            elif choice == "3":
                clear_screen()
                print_header()
                added = self.account_mgr.import_accounts_file()
                if added > 0 and self.riot_client and self.riot_client.is_valid():
                    console.print()
                    if prompt_confirm(f"Auto-resolve display names for {added} new account(s)? (requires login to each)"):
                        self.resolve_display_names()
                    else:
                        pause()
            elif choice == "4":
                clear_screen()
                print_header()
                self.account_mgr.remove_account()
            elif choice == "5":
                clear_screen()
                print_header()
                self.account_mgr.view_account_details()
            elif choice == "6":
                clear_screen()
                print_header()
                self.account_mgr.export_ranked_ready()
            elif choice == "0":
                break
            else:
                print_status("Invalid option.", "error")
                pause()
    
    def _smart_login(self, account_idx: int, launch_game: bool = False) -> bool:
        """
        Try login with smart fallback strategy:
        1. Silent login with saved cookies
        2. Refresh cookies + silent login retry
        3. Fall back to GUI automation
        
        Returns True if login succeeded.
        """
        accounts = self.data_store.load_accounts()
        if account_idx < 0 or account_idx >= len(accounts):
            print_status("Invalid account index.", "error")
            return False
        
        account = accounts[account_idx]
        username = account["username"]
        password = account["password"]
        cookies = account.get("cookies", {})
        
        # Strategy 1: Silent login with existing cookies
        if cookies:
            if self.riot_client.silent_login(cookies, launch_game=launch_game):
                print_status("Logged in silently using saved session!", "success")
                return True
            
            # Strategy 2: Refresh expired cookies and retry
            print_status("Session expired. Attempting cookie refresh...", "wait")
            refreshed = self.riot_client.session_mgr.refresh_cookies(cookies)
            if refreshed:
                self.data_store.update_account(account_idx, {"cookies": refreshed})
                if self.riot_client.silent_login(refreshed, launch_game=launch_game):
                    print_status("Logged in with refreshed session!", "success")
                    return True
        
        # Strategy 3: Fall back to GUI automation
        print_status("No valid session found. Using UI automation...", "info")
        success, new_cookies = self.riot_client.auto_login(username, password, launch_game=launch_game)
        if success and new_cookies:
            self.data_store.update_account(account_idx, {"cookies": new_cookies})
        return success
    
    def _auto_login(self):
        """Auto-login flow."""
        clear_screen()
        print_header()
        
        if not self.riot_client or not self.riot_client.is_valid():
            print_error_panel(
                "Riot Client Not Found",
                "Please configure the Riot Client path in Settings."
            )
            pause()
            return
        
        accounts = self.data_store.load_accounts()
        idx = show_auto_login_menu(accounts)
        
        if idx is None:
            return
        
        account = accounts[idx]
        username = account["username"]
        password = account["password"]
        display = account.get("display_name") or username
        
        console.print(get_section_title(f"Auto Login: {display}", "🎮"))
        
        if not prompt_confirm(f"Login to '{display}'?"):
            return
        
        # Smart login: silent → refresh → GUI automation
        success = self._smart_login(idx, launch_game=False)
        
        if success:
            print_success_panel("Login Initiated", "Riot Client should be logging in now.")
            
            # Try to resolve display name if not set
            if not account.get("display_name") and self.resolver:
                console.print()
                print_status("Attempting to resolve display name...", "wait")
                
                result = self.resolver.wait_and_resolve(timeout=45)
                if result:
                    self.data_store.update_account(idx, {
                        "display_name": result["game_name"],
                        "tag": result["game_tag"],
                        "puuid": result.get("puuid", ""),
                    })
                    print_success_panel(
                        "Display Name Resolved",
                        f"{result['game_name']}#{result['game_tag']}"
                    )
                else:
                    print_status("Could not resolve display name. Try 'Refresh Data' later.", "warning")
        else:
            print_error_panel(
                "Login Failed",
                "Auto-login could not complete.\n"
                "Make sure Riot Client is installed and accessible."
            )
        
        pause()
    
    def _refresh_data(self):
        """Refresh account data from HenrikDev API or update login sessions."""
        from ui.menus import show_refresh_menu
        choice = show_refresh_menu()
        
        if choice == "2":
            # Force resolve display names will also fetch cookies
            self.resolve_display_names(force_all=True)
            return
        elif choice == "3":
            self._refresh_via_ui_login()
            return
        elif choice != "1":
            return
            
        clear_screen()
        print_header()
        console.print(get_section_title("Refresh Account Stats", "📈"))
        
        if not self.henrik_api:
            print_error_panel(
                "API Not Configured",
                "No API key configured. Set it up in Settings."
            )
            pause()
            return
        
        accounts = self.data_store.load_accounts()
        
        if not accounts:
            print_status("No accounts to refresh.", "warning")
            pause()
            return
        
        # Check how many have display names
        with_names = sum(1 for a in accounts if a.get("display_name") and a.get("tag"))
        without_names = len(accounts) - with_names
        
        print_status(f"Total: {len(accounts)} | Ready: {with_names}", "info")
        
        if without_names > 0:
            print_status(
                f"{without_names} account(s) need display names first.",
                "warning",
            )
        
        if with_names == 0:
            print_error_panel(
                "No Queryable Accounts",
                "No accounts have display names set.\n"
                "Use Auto Login first to resolve display names,\n"
                "or the API won't know which accounts to look up."
            )
            pause()
            return
        
        print_status(f"Refreshing {with_names} account(s)...", "wait")
        console.print()
        
        # Invalidate cache to ensure fresh data
        self.data_store.invalidate_cache()
        
        # Reload accounts after cache invalidation
        accounts = self.data_store.load_accounts()
        
        stats = self.henrik_api.batch_refresh(accounts, self.data_store)
        
        console.print()
        
        if stats["updated"] > 0:
            # Invalidate cache to ensure fresh display
            self.data_store.invalidate_cache()
            
            print_success_panel(
                "Refresh Complete",
                f"Updated: {stats['updated']}\n"
                f"Failed: {stats['failed']}\n"
                f"Skipped (no display name): {stats['skipped']}"
            )
        
        if stats["errors"]:
            console.print("\n  [error]Errors:[/error]")
            for err in stats["errors"]:
                console.print(f"    [muted]• {err}[/muted]")
        
        pause()
    
    def _mark_fwotd(self):
        """Mark FWOTD as done for an account."""
        clear_screen()
        print_header()
        
        accounts = self.data_store.load_accounts()
        idx = show_fwotd_menu(accounts)
        
        if idx is None:
            return
        
        account = accounts[idx]
        display = account.get("display_name") or account.get("username", "Unknown")
        
        if self.session_mgr.is_fwotd_available(account):
            if prompt_confirm(f"Mark FWOTD done for '{display}'?"):
                self.session_mgr.mark_fwotd_done(idx)
                print_success_panel(
                    "FWOTD Marked ✔",
                    f"'{display}' FWOTD completed.\n"
                    f"Next FWOTD available in ~22 hours."
                )
        else:
            remaining = self.session_mgr.get_time_until_fwotd(account)
            if remaining:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                print_status(
                    f"FWOTD not available yet. {hours}h {minutes}m remaining.",
                    "warning",
                )
            else:
                print_status("FWOTD status unknown.", "warning")
        
        pause()
    
    def _start_suffering(self):
        """Start Suffering: auto-queue FWOTD across all ready accounts."""
        clear_screen()
        print_header()
        
        # Check Riot Client
        if not self.riot_client or not self.riot_client.is_valid():
            print_error_panel(
                "Riot Client Not Found",
                "Please configure the Riot Client path in Settings."
            )
            pause()
            return
        
        # Load accounts
        accounts = self.data_store.load_accounts()
        if not accounts:
            print_status("No accounts available. Add accounts first.", "warning")
            pause()
            return
        
        # Build ready/not-ready lists (same logic as dashboard)
        ready_accounts = []  # list of (original_index, account)
        for i, acc in enumerate(accounts):
            if acc.get("status") == "ranked_ready":
                continue
            if self.session_mgr.is_fwotd_available(acc):
                ready_accounts.append((i, acc))
        
        # Sort by level (lowest first)
        ready_accounts.sort(key=lambda x: x[1].get("level", 0))
        
        # Show dashboard
        console.print(build_suffering_dashboard(accounts, self.session_mgr))
        console.print()
        
        if not ready_accounts:
            print_status("No accounts have FWOTD available right now. Come back later!", "warning")
            pause()
            return
        
        print_status(f"{len(ready_accounts)} account(s) ready for FWOTD.", "info")
        
        if not prompt_confirm(f"Start the suffering queue?"):
            return
        
        # Process queue
        completed = 0
        total = len(ready_accounts)
        
        for queue_pos, (orig_idx, acc) in enumerate(ready_accounts):
            display = acc.get("display_name") or acc.get("username", "Unknown")
            tag = acc.get("tag", "")
            display_full = f"{display}#{tag}" if display and tag else display
            
            clear_screen()
            print_header()
            console.print(get_section_title("Start Suffering", "🔥"))
            console.print()
            
            # Progress indicator
            from rich.panel import Panel
            from rich.text import Text as RichText
            
            progress = RichText()
            progress.append(f"  Account ", style="#768079")
            progress.append(f"{queue_pos + 1}/{total}", style="bold #FF4655")
            progress.append(f"  │  ", style="#3a3a3a")
            progress.append(f"{display_full}", style="bold #ECE8E1")
            progress.append(f"  │  ", style="#3a3a3a")
            progress.append(f"Lv.{acc.get('level', 0)}", style="#768079")
            console.print(Panel(
                progress,
                border_style="#FF4655",
                padding=(0, 2),
            ))
            console.print()
            
            # Auto-login: silent → refresh → GUI automation
            print_status(f"Logging into {display_full}...", "wait")
            success = self._smart_login(orig_idx, launch_game=True)
            
            if not success:
                print_error_panel(
                    "Login Failed",
                    f"Could not login to '{display_full}'.\n"
                    "Skipping this account."
                )
                console.input("\n  [muted]Press Enter to continue to next account...[/muted]")
                continue
            
            print_success_panel("Login Submitted", f"Logged into {display_full}")
            console.print()
            
            # Try to resolve/update display name via Riot Client local API
            if self.resolver:
                print_status("Resolving account info...", "wait")
                resolved = self.resolver.wait_and_resolve(timeout=30)
                if resolved:
                    update_data = {
                        "display_name": resolved["game_name"],
                        "tag": resolved["game_tag"],
                        "puuid": resolved.get("puuid", ""),
                    }
                    self.data_store.update_account(orig_idx, update_data)
                    display_full = f"{resolved['game_name']}#{resolved['game_tag']}"
                    print_status(f"Account resolved: {display_full}", "success")
                else:
                    print_status("Could not resolve display name.", "warning")
            
            # Wait for Valorant to launch
            print_status("Waiting for Valorant to launch...", "wait")
            game_launched = self.riot_client.wait_for_valorant_launch(timeout=180)
            
            # Wait for user to finish FWOTD
            console.print(f"  [bold #F39C12]⏳ Play your FWOTD game![/bold #F39C12]")
            console.print(f"  [#768079]Press [bold #FF4655]Enter[/bold #FF4655] when you're done...[/#768079]")
            console.input("")

            # ── Fetch Level & FWOTD from Valorant local API ──────────
            # Invalidate cache to ensure we read the latest saved puuid/region
            self.data_store.invalidate_cache()
            acc_fresh = self.data_store.load_accounts()[orig_idx]
            puuid  = acc_fresh.get("puuid", "")
            region = acc_fresh.get("region", "") or "eu"

            if puuid and self.val_api:
                print_status("Fetching latest Level & XP from Valorant API...", "wait")
                xp_data = self.val_api.get_level_and_fwotd(puuid, region, max_wait=15)
                if xp_data:
                    old_level = acc_fresh.get("level", 0)
                    new_level = xp_data["level"]
                    level_diff = new_level - old_level

                    # Always mark FWOTD done since user confirmed finishing
                    self.session_mgr.mark_fwotd_done(orig_idx)
                    self.data_store.update_account(orig_idx, {
                        "level": new_level,
                        "xp":    xp_data.get("xp", 0),
                    })
                    self.data_store.invalidate_cache()

                    # Build status message with XP bar
                    fwotd_note = "FWOTD ✔ (confirmed via API)" if xp_data["fwotd_done"] else "FWOTD ✔ (marked manually)"

                    level_note = f"Lv.{new_level}"
                    if level_diff > 0:
                        level_note += f" [bold #2ECC71](+{level_diff})[/bold #2ECC71]"
                    elif level_diff == 0:
                        level_note += " [#768079](no change)[/#768079]"

                    xp_cur     = xp_data.get("xp", 0)
                    xp_to_next = xp_data.get("xp_to_next", 5000)
                    bar_width  = 10
                    filled     = round((xp_cur / 5000) * bar_width) if xp_cur > 0 else 0
                    xp_bar     = "█" * filled + "░" * (bar_width - filled)

                    console.print(
                        f"  [bold #FF4655]●[/bold #FF4655] Level: {level_note}  "
                        f"│  XP: [#FF4655]{xp_bar}[/#FF4655] {xp_cur:,}/5,000 "
                        f"([#2ECC71]{xp_to_next:,} to next[/#2ECC71])  │  {fwotd_note}"
                    )
                else:
                    # API unreachable (game closed?) → fallback: just mark done
                    print_status("API unavailable – FWOTD marked manually.", "warning")
                    self.session_mgr.mark_fwotd_done(orig_idx)
            else:
                # No PUUID available
                self.session_mgr.mark_fwotd_done(orig_idx)

            completed += 1
            
            print_success_panel(
                "FWOTD Marked ✔",
                f"'{display_full}' FWOTD completed. ({completed}/{total})"
            )
            
            # If more accounts remain, kill processes for next login
            if queue_pos < total - 1:
                console.print()
                print_status("Closing Riot Client for next account...", "wait")
                self.riot_client.kill_riot_processes()
                print_status("Ready for next account!", "success")
                import time
                time.sleep(1)
        
        # Final summary
        clear_screen()
        print_header()
        
        from rich.panel import Panel
        from rich.text import Text as RichText
        
        summary = RichText()
        summary.append(f"\n  Accounts Completed:  ", style="#768079")
        summary.append(f"{completed}/{total}\n", style=f"bold #2ECC71")
        summary.append(f"  Skipped (failed):    ", style="#768079")
        summary.append(f"{total - completed}\n", style="bold #E74C3C" if total - completed > 0 else "#768079")
        
        console.print(Panel(
            summary,
            title="[bold #FF4655]🔥 Suffering Complete![/bold #FF4655]",
            border_style="#FF4655",
            padding=(1, 2),
        ))
        
        pause()
    
    def _take_proofs(self):
        """Take screenshot proofs of the queue screen for all accounts."""
        clear_screen()
        print_header()
        
        # Check Riot Client
        if not self.riot_client or not self.riot_client.is_valid():
            print_error_panel(
                "Riot Client Not Found",
                "Please configure the Riot Client path in Settings."
            )
            pause()
            return
        
        # Load accounts
        accounts = self.data_store.load_accounts()
        if not accounts:
            print_status("No accounts available. Add accounts first.", "warning")
            pause()
            return
        
        if not prompt_confirm(f"Take proofs for {len(accounts)} account(s)? This will take some time."):
            return
            
        import time
        from datetime import datetime
        from config.settings import PROOFS_DIR, VALORANT_LOAD_DELAY, PLAY_BUTTON_CLICK_DELAY
        from rich.panel import Panel
        from rich.text import Text as RichText
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_proofs_dir = os.path.join(PROOFS_DIR, timestamp)
        os.makedirs(session_proofs_dir, exist_ok=True)
        
        completed = 0
        failed = 0
        failed_accounts = []
        total = len(accounts)
        
        for pos, acc in enumerate(accounts):
            username = acc["username"]
            password = acc["password"]
            
            clear_screen()
            print_header()
            console.print(get_section_title("Take Proofs", "📸"))
            console.print()
            
            # Progress indicator
            progress = RichText()
            progress.append(f"  Account ", style="#768079")
            progress.append(f"{pos + 1}/{total}", style="bold #FF4655")
            progress.append(f"  │  ", style="#3a3a3a")
            progress.append(f"{username}", style="bold #ECE8E1")
            progress.append(f"  │  ", style="#3a3a3a")
            progress.append(f"Lv.{acc.get('level', 0)}", style="#768079")
            console.print(Panel(progress, border_style="#FF4655", padding=(0, 2)))
            console.print()
            
            # Auto-login: silent → refresh → GUI automation
            print_status(f"Logging into {username}...", "wait")
            success = self._smart_login(pos, launch_game=True)
            
            if not success:
                print_error_panel("Login Failed", f"Could not login to '{username}'. Skipping.")
                failed += 1
                failed_accounts.append(username)
                time.sleep(3)
                continue
                
            print_success_panel("Login Submitted", f"Logged into {username}")
            
            # Wait for Valorant to launch
            print_status("Waiting for Valorant to launch...", "wait")
            game_launched = self.riot_client.wait_for_valorant_launch(timeout=180)
            
            if not game_launched:
                print_error_panel("Launch Failed", "Valorant didn't launch. Skipping.")
                failed += 1
                failed_accounts.append(username)
                self.riot_client.kill_riot_processes()
                time.sleep(3)
                continue
                
            # Wait for game to load
            print_status(f"Waiting {VALORANT_LOAD_DELAY}s for game to load...", "wait")
            time.sleep(VALORANT_LOAD_DELAY)
            
            # Click PLAY button
            print_status("Clicking PLAY button...", "wait")
            self.riot_client.click_valorant_play_button()
            
            # Wait for Queue Screen
            print_status(f"Waiting {PLAY_BUTTON_CLICK_DELAY}s for Queue screen...", "wait")
            time.sleep(PLAY_BUTTON_CLICK_DELAY)
            
            # Take screenshot
            print_status("Taking screenshot...", "wait")
            save_path = os.path.join(session_proofs_dir, f"{username}.png")
            if self.riot_client.take_screenshot(save_path):
                print_status(f"Screenshot saved: {username}.png", "success")
                completed += 1
            else:
                print_status("Failed to take screenshot.", "error")
                failed += 1
                failed_accounts.append(username)
                
            # Close processes for next account
            if pos < total - 1:
                print_status("Closing Riot Client for next account...", "wait")
                self.riot_client.kill_riot_processes()
                time.sleep(3)
                
        # Final Summary
        clear_screen()
        print_header()
        
        summary = RichText()
        summary.append(f"\n  Successful:  ", style="#768079")
        summary.append(f"{completed}/{total}\n", style="bold #2ECC71")
        summary.append(f"  Failed:      ", style="#768079")
        summary.append(f"{failed}\n\n", style="bold #E74C3C" if failed > 0 else "#768079")
        summary.append(f"  Folder Path: ", style="#768079")
        summary.append(f"{session_proofs_dir}\n", style="#3498DB")
        
        if failed_accounts:
            summary.append(f"\n  Failed Accounts:\n", style="#E74C3C")
            for acc in failed_accounts:
                summary.append(f"  - {acc}\n", style="#E74C3C")
                
        console.print(Panel(
            summary,
            title="[bold #FF4655]📸 Proofs Complete![/bold #FF4655]",
            border_style="#FF4655",
            padding=(1, 2),
        ))
        
        pause()
    
    def resolve_display_names(self, force_all: bool = False):
        """Auto-login to unresolved accounts to get their display names and extract cookies."""
        clear_screen()
        print_header()
        console.print(get_section_title("Update Accounts & Cookies", "🔍"))
        console.print()
        
        accounts = self.data_store.load_accounts()
        
        # Find accounts that don't have proper display names or if forced
        unresolved = []
        for i, acc in enumerate(accounts):
            if force_all:
                unresolved.append((i, acc))
                continue
                
            display = acc.get("display_name", "")
            tag = acc.get("tag", "")
            username = acc.get("username", "")
            # Consider unresolved if: no display name, or display matches username, or no tag, or missing cookies
            if not display or not tag or display == username or not acc.get("cookies"):
                unresolved.append((i, acc))
        
        if not unresolved:
            print_status("All accounts already have display names resolved!", "success")
            pause()
            return
        
        total = len(unresolved)
        resolved_count = 0
        failed_count = 0
        
        print_status(f"{total} account(s) need display name resolution.", "info")
        console.print()
        
        from rich.panel import Panel
        from rich.text import Text as RichText
        import time
        
        for pos, (orig_idx, acc) in enumerate(unresolved):
            username = acc["username"]
            password = acc["password"]
            
            # Progress
            progress = RichText()
            progress.append(f"  Resolving ", style="#768079")
            progress.append(f"{pos + 1}/{total}", style="bold #FF4655")
            progress.append(f"  │  ", style="#3a3a3a")
            progress.append(f"{username}", style="bold #ECE8E1")
            console.print(Panel(
                progress,
                border_style="#3a3a3a",
                padding=(0, 2),
            ))
            
            # Smart login: silent → refresh → GUI automation
            print_status(f"Logging into {username} to extract data...", "wait")
            success = self._smart_login(orig_idx, launch_game=False)
            
            if not success:
                print_status(f"Failed to login to {username}. Skipping.", "error")
                failed_count += 1
                continue
            
            # Resolve display name
            if self.resolver:
                print_status("Resolving display name...", "wait")
                result = self.resolver.wait_and_resolve(timeout=30)
                
                if result:
                    self.data_store.update_account(orig_idx, {
                        "display_name": result["game_name"],
                        "tag": result["game_tag"],
                        "puuid": result.get("puuid", ""),
                    })
                    resolved_count += 1
                    print_success_panel(
                        "Resolved ✔",
                        f"{username} → {result['game_name']}#{result['game_tag']}"
                    )
                else:
                    print_status(f"Could not resolve {username}.", "warning")
                    failed_count += 1
            
            # Kill processes for next account
            if pos < total - 1:
                print_status("Waiting 3s before next account...", "wait")
                self.riot_client.kill_riot_processes()
                time.sleep(3)
            
            console.print()
        
        # Summary
        clear_screen()
        print_header()
        
        from rich.panel import Panel
        from rich.text import Text as RichText
        
        summary = RichText()
        summary.append(f"\n  Resolved:  ", style="#768079")
        summary.append(f"{resolved_count}/{total}\n", style="bold #2ECC71")
        summary.append(f"  Failed:    ", style="#768079")
        summary.append(f"{failed_count}\n", style="bold #E74C3C" if failed_count > 0 else "#768079")
        
        console.print(Panel(
            summary,
            title="[bold #FF4655]🔍 Auto-Resolve Complete[/bold #FF4655]",
            border_style="#FF4655",
            padding=(1, 2),
        ))
        
        pause()
    
    def _refresh_via_ui_login(self):
        """
        Option 3 in Refresh Data: login to each account (silent → refresh → GUI)
        and update Level & FWOTD data directly from the Valorant local PVP API.
        No external API key required.
        """
        clear_screen()
        print_header()
        console.print(get_section_title("Update via UI Login", "🎮"))
        console.print()

        if not self.riot_client or not self.riot_client.is_valid():
            print_error_panel(
                "Riot Client Not Found",
                "Please configure the Riot Client path in Settings."
            )
            pause()
            return

        if not self.val_api:
            print_error_panel(
                "Valorant API Not Ready",
                "Could not initialize the Valorant local API client."
            )
            pause()
            return

        accounts = self.data_store.load_accounts()
        if not accounts:
            print_status("No accounts to update.", "warning")
            pause()
            return

        total = len(accounts)
        print_status(f"Will update {total} account(s) via UI login.", "info")
        console.print()

        if not prompt_confirm(f"Start updating {total} account(s)?"):
            return

        import time
        from rich.panel import Panel
        from rich.text import Text as RichText

        updated = 0
        failed  = 0

        for pos, acc in enumerate(accounts):
            username = acc["username"]
            display  = acc.get("display_name") or username
            tag      = acc.get("tag", "")
            display_full = f"{display}#{tag}" if tag else display

            clear_screen()
            print_header()
            console.print(get_section_title("Update via UI Login", "🎮"))
            console.print()

            progress = RichText()
            progress.append(f"  Account ", style="#768079")
            progress.append(f"{pos + 1}/{total}", style="bold #FF4655")
            progress.append(f"  │  ", style="#3a3a3a")
            progress.append(f"{display_full}", style="bold #ECE8E1")
            progress.append(f"  │  ", style="#3a3a3a")
            progress.append(f"Lv.{acc.get('level', 0)}", style="#768079")
            console.print(Panel(progress, border_style="#FF4655", padding=(0, 2)))
            console.print()

            # ── Login ─────────────────────────────────────────
            print_status(f"Logging in to {display_full}...", "wait")
            success = self._smart_login(pos, launch_game=False)

            if not success:
                print_error_panel("Login Failed", f"Could not login to '{display_full}'. Skipping.")
                failed += 1
                if pos < total - 1:
                    self.riot_client.kill_riot_processes()
                    time.sleep(2)
                continue

            print_status("Login successful!", "success")

            # ── Resolve display name & PUUID if missing ────────
            self.data_store.invalidate_cache()
            acc = self.data_store.load_accounts()[pos]
            if self.resolver and (not acc.get("puuid") or not acc.get("display_name")):
                print_status("Resolving display name...", "wait")
                result = self.resolver.wait_and_resolve(timeout=20)
                if result:
                    puuid_resolved = result.get("puuid", "")
                    # Fallback: get PUUID from entitlements token (subject field)
                    if not puuid_resolved and self.val_api:
                        tokens = self.val_api._get_access_token_and_entitlements()
                        if tokens:
                            # subject is in the entitlements response
                            auth_info = self.val_api._get_local_auth()
                            if auth_info:
                                import requests as _req
                                try:
                                    r = _req.get(
                                        f"{auth_info[0]}/entitlements/v1/token",
                                        auth=auth_info[1], verify=False, timeout=5
                                    )
                                    if r.status_code == 200:
                                        puuid_resolved = r.json().get("subject", "")
                                except Exception:
                                    pass

                    self.data_store.update_account(pos, {
                        "display_name": result["game_name"],
                        "tag":          result["game_tag"],
                        "puuid":        puuid_resolved,
                    })
                    self.data_store.invalidate_cache()
                    acc = self.data_store.load_accounts()[pos]
                    display_full = f"{acc['display_name']}#{acc.get('tag', '')}"
                    print_status(f"Resolved: {display_full} (PUUID: {'✔' if puuid_resolved else '✗'})", "success")

            # ── Fetch XP data ──────────────────────────────────
            puuid  = acc.get("puuid", "")
            region = acc.get("region", "eu")

            if not puuid:
                print_status("No PUUID available – cannot fetch XP data.", "warning")
                failed += 1
                if pos < total - 1:
                    self.riot_client.kill_riot_processes()
                    time.sleep(2)
                continue

            print_status("Fetching Level & XP from Valorant API...", "wait")
            xp_data = self.val_api.get_level_and_fwotd(puuid, region, max_wait=25)

            if xp_data:
                update_fields = {
                    "level": xp_data["level"],
                    "xp":    xp_data.get("xp", 0),
                }

                if xp_data["fwotd_done"]:
                    self.session_mgr.mark_fwotd_done(pos)
                    fwotd_status = "✔ Done today"
                else:
                    fwotd_status = "○ Not done yet"

                self.data_store.update_account(pos, update_fields)

                xp_cur     = xp_data.get("xp", 0)
                xp_to_next = xp_data.get("xp_to_next", 5000)
                print_status(
                    f"Updated → Lv.{xp_data['level']} | "
                    f"XP: {xp_cur:,}/5,000 ({xp_to_next:,} to next) | "
                    f"FWOTD: {fwotd_status}",
                    "success",
                )
                updated += 1
            else:
                print_status("Could not fetch XP data.", "error")
                failed += 1

            # ── Prepare for next account ───────────────────────
            if pos < total - 1:
                print_status("Closing Riot Client for next account...", "wait")
                self.riot_client.kill_riot_processes()
                time.sleep(2)

            console.print()

        # ── Final summary ──────────────────────────────────────
        clear_screen()
        print_header()

        sum_text = RichText()
        sum_text.append(f"\n  Updated:  ", style="#768079")
        sum_text.append(f"{updated}/{total}\n", style="bold #2ECC71")
        sum_text.append(f"  Failed:   ", style="#768079")
        sum_text.append(
            f"{failed}\n",
            style="bold #E74C3C" if failed > 0 else "#768079",
        )

        console.print(Panel(
            sum_text,
            title="[bold #FF4655]🎮 UI Login Update Complete[/bold #FF4655]",
            border_style="#FF4655",
            padding=(1, 2),
        ))

        pause()

    def _settings_loop(self):
        """Settings submenu loop."""
        while True:
            clear_screen()
            print_header()
            
            choice = show_settings_menu()
            
            if choice == "1":
                self._change_riot_path()
            elif choice == "2":
                self._change_valorant_path()
            elif choice == "3":
                self._change_api_key()
            elif choice == "4":
                wizard = SetupWizard(self.data_store)
                wizard.run()
                self._init_services()
            elif choice == "5":
                self._view_settings()
            elif choice == "0":
                break
            else:
                print_status("Invalid option.", "error")
                pause()
    
    def _change_riot_path(self):
        """Change Riot Client path."""
        clear_screen()
        print_header()
        console.print(get_section_title("Change Riot Client Path", "📁"))
        
        config = self.data_store.load_config()
        current = config.get("riot_client_path", "Not set")
        print_status(f"Current: {current}", "info")
        
        new_path = prompt_input("Enter new path")
        if new_path:
            new_path = new_path.strip().strip('"').strip("'")
            test = RiotClient(new_path)
            if test.is_valid():
                config["riot_client_path"] = new_path
                self.data_store.save_config(config)
                self.riot_client = test
                print_success_panel("Path Updated", f"New path: {new_path}")
            else:
                print_error_panel("Invalid Path", "RiotClientServices.exe not found.")
        
        pause()
    
    def _change_valorant_path(self):
        """Change Valorant Game path."""
        clear_screen()
        print_header()
        console.print(get_section_title("Change Valorant Path", "🎮"))
        
        config = self.data_store.load_config()
        current = config.get("valorant_path", "Auto-Detect")
        print_status(f"Current: {current}", "info")
        console.print("  [muted]Example: C:\\Riot Games\\VALORANT\\live\\VALORANT.exe[/muted]\n")
        
        new_path = prompt_input("Enter new path (leave empty for auto-detect)")
        if new_path is not None:
            new_path = new_path.strip().strip('"').strip("'")
            if not new_path or os.path.exists(new_path) and new_path.lower().endswith('.exe'):
                config["valorant_path"] = new_path
                self.data_store.save_config(config)
                if self.riot_client:
                    self.riot_client.valorant_path = new_path
                print_success_panel("Path Updated", f"New path: {new_path if new_path else 'Auto-Detect'}")
            else:
                print_error_panel("Invalid Path", "File not found or not an .exe")
        
        pause()
    
    def _change_api_key(self):
        """Change HenrikDev API key."""
        clear_screen()
        print_header()
        console.print(get_section_title("Change API Key", "🔑"))
        
        config = self.data_store.load_config()
        current = config.get("api_key", "Not set")
        masked = current[:10] + "..." if len(current) > 10 else current
        print_status(f"Current: {masked}", "info")
        
        new_key = prompt_input("Enter new API key")
        if new_key:
            config["api_key"] = new_key
            self.data_store.save_config(config)
            self.henrik_api = HenrikAPI(new_key)
            print_success_panel("API Key Updated", "New key saved.")
        
        pause()
    
    def _view_settings(self):
        """View current settings."""
        clear_screen()
        print_header()
        console.print(get_section_title("Current Settings", "📋"))
        
        config = self.data_store.load_config()
        
        from rich.text import Text
        from rich.panel import Panel
        
        info = Text()
        
        riot_path = config.get("riot_client_path", "Not set")
        val_path = config.get("valorant_path", "Auto-Detect")
        api_key = config.get("api_key", "Not set")
        masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else api_key
        setup = "✅ Complete" if config.get("setup_complete") else "❌ Incomplete"
        accounts_count = len(self.data_store.load_accounts())
        
        riot_valid = "✅" if self.riot_client and self.riot_client.is_valid() else "❌"
        val_valid = "✅" if os.path.exists(val_path) else "⏳ (Auto)" if not config.get("valorant_path") else "❌"
        
        info.append(f"\n  Setup Status:     ", style="#768079")
        info.append(f"{setup}\n", style="#ECE8E1")
        info.append(f"  Riot Client:      ", style="#768079")
        info.append(f"{riot_path} {riot_valid}\n", style="#ECE8E1")
        info.append(f"  Valorant Path:    ", style="#768079")
        info.append(f"{val_path} {val_valid}\n", style="#ECE8E1")
        info.append(f"  API Key:          ", style="#768079")
        info.append(f"{masked_key}\n", style="#ECE8E1")
        info.append(f"  Total Accounts:   ", style="#768079")
        info.append(f"{accounts_count}\n", style="#ECE8E1")
        info.append(f"  App Version:      ", style="#768079")
        info.append(f"{APP_VERSION}\n", style="#ECE8E1")
        
        console.print(Panel(
            info,
            title="[bold #FF4655]⚙️ Settings[/bold #FF4655]",
            border_style="#FF4655",
            padding=(1, 2),
        ))
        
        pause()


# ─── Entry Point ─────────────────────────────────────────────
def main():
    """Application entry point."""
    # Set console title on Windows
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(f"{APP_NAME} - {APP_FULL_NAME} v{APP_VERSION}")
    except Exception:
        pass
    
    app = VAMApp()
    app.run()


if __name__ == "__main__":
    main()
