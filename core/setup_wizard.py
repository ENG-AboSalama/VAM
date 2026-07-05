"""
VAM - Setup Wizard
First-run configuration wizard.
"""

import os
from core.data_store import DataStore
from services.riot_client import RiotClient
from services.henrik_api import HenrikAPI
from ui.console import (
    console, clear_screen, print_header, print_separator,
    print_status, print_step, prompt_input, prompt_confirm,
    print_success_panel, print_error_panel, pause,
)
from ui.banners import get_setup_banner, get_logo
from config.settings import (
    HENRIK_API_KEY, RIOT_CLIENT_DEFAULT_PATH, 
    APP_NAME, APP_FULL_NAME,
)


class SetupWizard:
    """First-run setup wizard for VAM configuration."""
    
    TOTAL_STEPS = 4
    
    def __init__(self, data_store: DataStore):
        self.store = data_store
        self.config = {}
    
    def run(self) -> bool:
        """
        Run the setup wizard.
        Returns True if setup completed successfully.
        """
        clear_screen()
        console.print(get_logo(), justify="center")
        console.print()
        console.print(get_setup_banner())
        console.print()
        pause("Press Enter to start setup...")
        
        # Step 1: Riot Client Path
        riot_path = self._step_riot_client()
        if riot_path is None:
            return False
        self.config["riot_client_path"] = riot_path
        
        # Step 2: API Key
        api_key = self._step_api_key()
        if api_key is None:
            return False
        self.config["api_key"] = api_key
        
        # Step 3: Import Accounts (optional)
        self._step_import_accounts()
        
        # Step 4: Confirmation
        return self._step_confirm()
    
    def _step_riot_client(self) -> str | None:
        """Step 1: Configure Riot Client path."""
        clear_screen()
        print_step(1, self.TOTAL_STEPS, "Riot Client Path")
        
        # Try auto-detection first
        riot_client = RiotClient()
        
        if riot_client.is_valid():
            print_success_panel(
                "Auto-Detected",
                f"Riot Client found at:\n{riot_client.riot_path}"
            )
            
            if prompt_confirm("Use this path?"):
                return riot_client.riot_path
        else:
            print_status("Riot Client not found at default locations.", "warning")
        
        # Manual input
        while True:
            path = prompt_input(
                "Enter Riot Client folder path",
                RIOT_CLIENT_DEFAULT_PATH,
            )
            
            test_client = RiotClient(path)
            if test_client.is_valid():
                print_status(f"Riot Client found: {test_client.exe_path}", "success")
                return path
            else:
                print_status(
                    f"RiotClientServices.exe not found in '{path}'.", "error"
                )
                if not prompt_confirm("Try another path?"):
                    print_status("Skipping Riot Client setup. Auto-login won't work.", "warning")
                    return path  # Save anyway, user can fix later
    
    def _step_api_key(self) -> str | None:
        """Step 2: Configure HenrikDev API key."""
        clear_screen()
        print_step(2, self.TOTAL_STEPS, "HenrikDev API Key")
        
        console.print("\n  [#ECE8E1]The API key is used to fetch account levels and info.[/#ECE8E1]")
        console.print("  [muted]Get a free key at: https://api.henrikdev.xyz/dashboard/[/muted]")
        console.print("  [muted]Or join their Discord for instructions.[/muted]")
        
        # Use default key if available
        default_key = HENRIK_API_KEY
        
        api_key = prompt_input("Enter API Key", default_key)
        
        if not api_key:
            print_status("API key is required for account data fetching.", "warning")
            api_key = prompt_input("Enter API Key (required)")
            if not api_key:
                return HENRIK_API_KEY  # Fall back to default
        
        # Validate the key
        print_status("Validating API key...", "wait")
        api = HenrikAPI(api_key)
        
        if api.validate_api_key():
            print_status("API key is valid!", "success")
        else:
            print_status("Could not validate API key. It may still work.", "warning")
            if not prompt_confirm("Continue with this key?"):
                return self._step_api_key()
        
        return api_key
    
    def _step_import_accounts(self):
        """Step 3: Optional account import."""
        clear_screen()
        print_step(3, self.TOTAL_STEPS, "Import Accounts (Optional)")
        
        console.print("\n  [#ECE8E1]You can import accounts now or add them later.[/#ECE8E1]")
        console.print("  [muted]Supported format: username:password (one per line)[/muted]")
        
        if not prompt_confirm("Import accounts from a file now?", default=False):
            print_status("Skipped. You can import accounts later from the main menu.", "info")
            return
        
        file_path = prompt_input("Enter file path")
        if not file_path:
            return
        
        file_path = file_path.strip().strip('"').strip("'")
        
        if not os.path.exists(file_path):
            print_error_panel("File Not Found", f"Cannot find: {file_path}")
            return
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            added, skipped = self.store.import_accounts(lines)
            
            if added > 0:
                print_success_panel(
                    "Import Complete",
                    f"Added: {added} account(s)\nSkipped: {skipped}"
                )
            else:
                print_status(f"No accounts imported. Skipped: {skipped}", "warning")
        except IOError as e:
            print_error_panel("Read Error", str(e))
    
    def _step_confirm(self) -> bool:
        """Step 4: Review and confirm setup."""
        clear_screen()
        print_step(4, self.TOTAL_STEPS, "Review & Confirm")
        
        accounts = self.store.load_accounts()
        
        from rich.text import Text
        from rich.panel import Panel
        
        summary = Text()
        summary.append("\n  Riot Client:  ", style="#768079")
        summary.append(f"{self.config.get('riot_client_path', 'Not set')}\n", style="#ECE8E1")
        summary.append("  API Key:      ", style="#768079")
        key = self.config.get('api_key', '')
        masked = key[:10] + "..." + key[-4:] if len(key) > 14 else key
        summary.append(f"{masked}\n", style="#ECE8E1")
        summary.append("  Accounts:     ", style="#768079")
        summary.append(f"{len(accounts)} loaded\n", style="#ECE8E1")
        
        console.print(Panel(
            summary,
            title="[bold #FF4655]Setup Summary[/bold #FF4655]",
            border_style="#FF4655",
            padding=(1, 2),
        ))
        
        if prompt_confirm("Save and complete setup?"):
            self.config["setup_complete"] = True
            self.store.save_config(self.config)
            
            print_success_panel(
                "Setup Complete! 🎉",
                "VAM is ready to use.\n"
                "You'll be redirected to the main menu."
            )
            pause()
            return True
        else:
            print_status("Setup cancelled. You can re-run it from settings.", "warning")
            pause()
            return False
