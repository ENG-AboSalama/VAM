"""
VAM - Menu System
All menu screens and navigation.
"""

from ui.console import (
    console, print_header, print_separator, print_status,
    prompt_input, prompt_confirm, pause, clear_screen,
    print_success_panel, print_error_panel,
)
from ui.banners import get_mini_header, get_section_title
from ui.tables import build_accounts_table, build_account_detail, build_summary_stats
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from ui.interactive import show_interactive_menu, get_key


def show_main_menu() -> str:
    """Display the main menu and return the user's choice."""
    options = [
        ("1", "📋", "Account Manager", "View, add, edit, and manage your accounts"),
        ("2", "🎮", "Auto Login", "Select an account and log in silently without typing"),
        ("3", "🔄", "Refresh Data", "Fetch latest account data and refresh sessions"),
        ("4", "📝", "Mark FWOTD Done", "Manually mark First Win of the Day as completed"),
        ("5", "⚙️", "Settings", "Configure app settings and API keys"),
        ("6", "🔥", "Start Suffering", "Auto-queue FWOTD across all ready accounts"),
        ("7", "📸", "Take Proofs!", "Login to each account, open game, and screenshot the queue screen"),
        ("0", "❌", "Exit", "Close VAM safely"),
    ]
    return show_interactive_menu("Main Menu", options, "✨")


def show_account_manager_menu() -> str:
    """Display the account manager submenu."""
    options = [
        ("1", "👁️", "View All Accounts", "Display a detailed table of all accounts"),
        ("2", "➕", "Add Account (Manual)", "Add a single account manually"),
        ("3", "📂", "Import Accounts (File)", "Import multiple accounts from a text file"),
        ("4", "🗑️", "Remove Account", "Delete an account from the system"),
        ("5", "🔍", "View Account Details", "See extended stats for a specific account"),
        ("6", "📤", "Export Ranked-Ready", "Export all accounts level 20+ to a file"),
        ("0", "🔙", "Back", "Return to Main Menu"),
    ]
    return show_interactive_menu("Account Manager", options, "📋")


def show_auto_login_menu(accounts: list[dict]) -> int | None:
    """Display account selection for auto-login. Returns account index or None."""
    if not accounts:
        print_status("No accounts available. Add accounts first.", "warning")
        pause()
        return None
        
    options = []
    for i, acc in enumerate(accounts):
        display = acc.get("display_name", "")
        tag = acc.get("tag", "")
        name = f"{display}#{tag}" if display and tag else acc.get("username", "N/A")
        level = acc.get("level", 0)
        options.append((str(i), "👤", name, f"Level: {level}"))
        
    options.append(("back", "🔙", "Back", "Return to Main Menu"))
    
    choice = show_interactive_menu("Auto Login", options, "🎮")
    if choice == "back":
        return None
    return int(choice)


def show_settings_menu() -> str:
    """Display settings submenu."""
    options = [
        ("1", "📁", "Change Riot Client Path", "Set the path to your Riot Client executable"),
        ("2", "🎯", "Change Valorant Path", "Set the path to your Valorant game executable"),
        ("3", "🔑", "Change API Key", "Update your HenrikDev API key"),
        ("4", "🔄", "Re-run Setup Wizard", "Run the initial setup configuration again"),
        ("5", "👁️", "View Current Settings", "Display all current configuration values"),
        ("0", "🔙", "Back", "Return to Main Menu"),
    ]
    return show_interactive_menu("Settings", options, "⚙️")


def show_fwotd_menu(accounts: list[dict]) -> int | None:
    """Display account selection for marking FWOTD done."""
    if not accounts:
        print_status("No accounts available.", "warning")
        pause()
        return None
        
    from ui.tables import _get_fwotd_display
    
    options = []
    for i, acc in enumerate(accounts):
        display = acc.get("display_name", "")
        tag = acc.get("tag", "")
        name = f"{display}#{tag}" if display and tag else acc.get("username", "N/A")
        fwotd = _get_fwotd_display(acc)
        options.append((str(i), "🏆", name, f"Status: {fwotd}"))
        
    options.append(("back", "🔙", "Back", "Return to Main Menu"))
    
    choice = show_interactive_menu("Mark FWOTD Done", options, "📝")
    if choice == "back":
        return None
    return int(choice)


def show_refresh_menu() -> str:
    """Display the refresh data submenu."""
    options = [
        ("1", "📊", "Refresh Account Stats", "Fast update for Levels & Ranks via HenrikDev API"),
        ("2", "🔑", "Refresh Login Info", "Deep update for Sessions & Cookies via Riot Client"),
        ("3", "🎮", "Update via UI Login", "Login to each account and update Level & FWOTD from Valorant API"),
        ("0", "🔙", "Cancel", "Return to Main Menu"),
    ]
    return show_interactive_menu("Refresh Menu", options, "🔄")
