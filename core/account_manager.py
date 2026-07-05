"""
VAM - Account Manager
High-level account management operations (orchestrates data_store + UI).
"""

import os
from core.data_store import DataStore
from ui.console import (
    console, prompt_input, prompt_confirm, pause,
    print_status, print_success_panel, print_error_panel,
    clear_screen, print_header
)
from ui.tables import build_accounts_table, build_account_detail, build_summary_stats
from ui.banners import get_section_title
from config.settings import AccountStatus, RANKED_READY_LEVEL


class AccountManager:
    """Manages account operations with UI integration."""
    
    def __init__(self, data_store: DataStore):
        self.store = data_store
    
    def view_all_accounts(self):
        """Display all accounts in a table with summary stats and interactive sorting."""
        sort_mode = "default"
        
        while True:
            clear_screen()
            print_header()
            
            accounts = self.store.load_accounts()
            
            # Apply sorting
            if sort_mode == "name":
                accounts.sort(key=lambda a: (a.get("display_name") or a.get("username", "")).lower())
            elif sort_mode == "level":
                accounts.sort(key=lambda a: (a.get("level", 0), a.get("xp", 0) or 0), reverse=True)
            elif sort_mode == "fwotd":
                from datetime import datetime
                def fwotd_key(acc):
                    val = acc.get("last_fwotd")
                    if not val:
                        return 0.0  # Ready immediately (sorts to the top)
                    try:
                        return datetime.fromisoformat(val).timestamp()
                    except ValueError:
                        return 0.0
                accounts.sort(key=fwotd_key)
            
            # Show summary stats
            console.print(build_summary_stats(accounts))
            console.print()
            
            # Determine title
            sort_titles = {
                "default": "Account Overview",
                "name": "Account Overview (Sorted by Name)",
                "level": "Account Overview (Sorted by Level)",
                "fwotd": "Account Overview (Sorted by FWOTD)",
            }
            
            # Show accounts table
            console.print(build_accounts_table(accounts, title=sort_titles[sort_mode]))
            
            # Prompt for sorting
            console.print("\n  [#768079]Sort by: [1] Name  [2] Level  [3] FWOTD  |  [0/Enter] Back[/#768079]")
            choice = prompt_input("Select an option").strip()
            
            if choice == "1":
                sort_mode = "name"
            elif choice == "2":
                sort_mode = "level"
            elif choice == "3":
                sort_mode = "fwotd"
            elif choice in ("0", ""):
                break
    
    def add_account_manual(self):
        """Add a single account manually."""
        console.print(get_section_title("Add Account", "➕"))
        
        username = prompt_input("Enter username")
        if not username:
            print_status("Username cannot be empty.", "error")
            pause()
            return
        
        password = prompt_input("Enter password")
        if not password:
            print_status("Password cannot be empty.", "error")
            pause()
            return
        
        result = self.store.add_account(username, password)
        if result:
            print_success_panel(
                "Account Added",
                f"Account '{username}' has been added successfully.\n"
                f"Use 'Refresh Data' to fetch display name and level."
            )
        else:
            print_error_panel(
                "Duplicate Account",
                f"Account with username '{username}' already exists."
            )
        pause()
    
    def import_accounts_file(self) -> int:
        """Import accounts from a text file. Returns number of accounts added."""
        console.print(get_section_title("Import Accounts", "📂"))
        
        console.print("\n  [muted]Supported formats:[/muted]")
        console.print("  [#ECE8E1]• username:password (one per line)[/#ECE8E1]")
        console.print("  [#ECE8E1]• username,password (CSV)[/#ECE8E1]")
        console.print("  [muted]Lines starting with # are ignored.[/muted]")
        
        file_path = prompt_input("Enter file path")
        if not file_path:
            print_status("No file path provided.", "error")
            pause()
            return 0
        
        # Clean path (handle quotes and whitespace)
        file_path = file_path.strip().strip('"').strip("'")
        
        if not os.path.exists(file_path):
            print_error_panel("File Not Found", f"Cannot find file: {file_path}")
            pause()
            return 0
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except IOError as e:
            print_error_panel("Read Error", f"Cannot read file: {e}")
            pause()
            return 0
        
        if not lines:
            print_status("File is empty.", "warning")
            pause()
            return 0
        
        added, skipped = self.store.import_accounts(lines)
        
        if added > 0:
            print_success_panel(
                "Import Complete",
                f"Successfully imported {added} account(s).\n"
                f"Skipped: {skipped} (duplicates or invalid format)."
            )
        else:
            print_error_panel(
                "Import Failed",
                f"No accounts were imported.\n"
                f"Skipped: {skipped} (duplicates or invalid format)."
            )
        
        return added
    
    def remove_account(self):
        """Remove an account by selection."""
        accounts = self.store.load_accounts()
        
        if not accounts:
            print_status("No accounts to remove.", "warning")
            pause()
            return
        
        console.print(get_section_title("Remove Account", "🗑️"))
        console.print(build_accounts_table(accounts, "Select Account to Remove"))
        
        choice = prompt_input("Enter account number (or 0 to cancel)")
        
        try:
            idx = int(choice) - 1
            if idx == -1:
                return
            
            acc = self.store.get_account_by_index(idx)
            if acc:
                name = acc.get("display_name") or acc.get("username", "Unknown")
                if prompt_confirm(f"Remove account '{name}'?", default=False):
                    self.store.remove_account(idx)
                    print_success_panel("Account Removed", f"'{name}' has been removed.")
                else:
                    print_status("Cancelled.", "info")
            else:
                print_status("Invalid account number.", "error")
        except ValueError:
            print_status("Invalid input.", "error")
        
        pause()
    
    def view_account_details(self):
        """View detailed info about a specific account."""
        accounts = self.store.load_accounts()
        
        if not accounts:
            print_status("No accounts available.", "warning")
            pause()
            return
        
        console.print(build_accounts_table(accounts, "Select Account"))
        
        choice = prompt_input("Enter account number (or 0 to cancel)")
        
        try:
            idx = int(choice) - 1
            if idx == -1:
                return
            
            acc = self.store.get_account_by_index(idx)
            if acc:
                console.print(build_account_detail(acc))
            else:
                print_status("Invalid account number.", "error")
        except ValueError:
            print_status("Invalid input.", "error")
        
        pause()
    
    def export_ranked_ready(self):
        """Export ranked-ready accounts to a file."""
        ready = self.store.export_ranked_ready()
        
        if not ready:
            print_status(
                "No ranked-ready accounts found (Level 20 needed).", "warning"
            )
            pause()
            return
        
        console.print(get_section_title(f"Export {len(ready)} Ranked-Ready Account(s)", "📤"))
        
        file_path = prompt_input("Enter output file path", "ranked_ready.txt")
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# VAM - Ranked Ready Accounts Export\n")
                f.write(f"# Exported: {__import__('datetime').datetime.now().isoformat()}\n")
                f.write(f"# Total: {len(ready)}\n\n")
                
                for acc in ready:
                    display = acc.get("display_name", "")
                    tag = acc.get("tag", "")
                    display_full = f"{display}#{tag}" if display and tag else "N/A"
                    
                    f.write(f"Display Name: {display_full}\n")
                    f.write(f"Username: {acc['username']}\n")
                    f.write(f"Password: {acc['password']}\n")
                    f.write(f"Level: {acc.get('level', 0)}\n")
                    f.write(f"Region: {acc.get('region', 'N/A')}\n")
                    f.write("---\n")
            
            print_success_panel(
                "Export Complete",
                f"Exported {len(ready)} account(s) to: {file_path}"
            )
        except IOError as e:
            print_error_panel("Export Failed", f"Cannot write file: {e}")
        
        pause()
