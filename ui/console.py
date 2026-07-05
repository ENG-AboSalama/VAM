"""
VAM - Console UI Setup
Rich console instance with Valorant-themed styling.
"""

from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from config.settings import COLORS, APP_VERSION, APP_DEVELOPER, APP_POWERED_BY

# ─── Custom Theme ────────────────────────────────────────────
vam_theme = Theme({
    "primary": COLORS["primary"],
    "accent": COLORS["accent"],
    "success": COLORS["success"],
    "warning": COLORS["warning"],
    "error": COLORS["error"],
    "info": COLORS["info"],
    "muted": COLORS["muted"],
    "highlight": COLORS["highlight"],
})

# ─── Global Console Instance ────────────────────────────────
console = Console(theme=vam_theme)
_current_status = None

def _stop_spinner_if_running():
    global _current_status
    if _current_status is not None:
        _current_status.stop()
        _current_status = None

def clear_screen():
    """Clear the console screen."""
    _stop_spinner_if_running()
    console.clear()


def print_header():
    """Print the VAM header with branding."""
    from ui.banners import get_logo
    clear_screen()
    console.print(get_logo(), justify="center")
    console.print()


def print_separator(char="─", style="primary"):
    """Print a styled separator line."""
    width = min(console.width, 80)
    console.print(char * width, style=style)


def print_status(message: str, status: str = "info", replace: bool = False):
    """Print a status message with icon. If status is 'wait', shows a loading spinner."""
    global _current_status
    icons = {
        "info": "ℹ️ ",
        "success": "✅",
        "warning": "⚠️ ",
        "error": "❌",
    }
    
    if status == "wait":
        if _current_status is None:
            _current_status = console.status(f"[bold #FF4655]{message}", spinner="dots")
            _current_status.start()
        else:
            _current_status.update(f"[bold #FF4655]{message}")
    else:
        _stop_spinner_if_running()
            
        icon = icons.get(status, "•")
        text = f"  {icon} {message}"
        console.print(text, style=status if status in vam_theme.styles else "")


def print_step(step_num: int, total: int, message: str):
    """Print a setup wizard step indicator."""
    console.print(
        f"\n  [primary]Step {step_num}/{total}[/primary]  [muted]│[/muted]  {message}",
    )
    print_separator("─", "muted")


def prompt_input(message: str, default: str = None, password: bool = False) -> str:
    """Prompt user for input with styling."""
    _stop_spinner_if_running()
    suffix = f" [muted]({default})[/muted]" if default else ""
    console.print(f"\n  [primary]▸[/primary] {message}{suffix}")
    
    if password:
        import getpass
        value = getpass.getpass("    → ")
    else:
        value = console.input("    [primary]→[/primary] ")
    
    if not value and default:
        return default
    return value.strip()


def prompt_choice(message: str, choices: list[str]) -> str:
    """Prompt user to choose from a list."""
    _stop_spinner_if_running()
    console.print(f"\n  [primary]▸[/primary] {message}")
    for i, choice in enumerate(choices, 1):
        console.print(f"    [primary][{i}][/primary] {choice}")
    
    while True:
        value = console.input("\n    [primary]→[/primary] ")
        try:
            idx = int(value) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        console.print("    [error]Invalid choice. Try again.[/error]")


def prompt_confirm(message: str, default: bool = True) -> bool:
    """Prompt user for yes/no confirmation."""
    _stop_spinner_if_running()
    hint = "[Y/n]" if default else "[y/N]"
    console.print(f"\n  [primary]▸[/primary] {message} [muted]{hint}[/muted]")
    value = console.input("    [primary]→[/primary] ").strip().lower()
    
    if not value:
        return default
    return value in ("y", "yes")


def print_error_panel(title: str, message: str):
    """Print an error in a styled panel."""
    panel = Panel(
        f"[error]{message}[/error]",
        title=f"[bold red]✖ {title}[/bold red]",
        border_style="red",
        padding=(1, 2),
    )
    console.print(panel)


def print_success_panel(title: str, message: str):
    """Print a success message in a styled panel."""
    panel = Panel(
        f"[success]{message}[/success]",
        title=f"[bold green]✔ {title}[/bold green]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)


def pause(message: str = "Press Enter to continue..."):
    """Pause and wait for user input."""
    _stop_spinner_if_running()
    console.input(f"\n  [muted]{message}[/muted]")
