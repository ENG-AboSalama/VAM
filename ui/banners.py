"""
VAM - ASCII Art Banners & Branding
"""

from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from config.settings import APP_VERSION, APP_DEVELOPER, APP_POWERED_BY


# ─── Main Logo ───────────────────────────────────────────────
LOGO_ART = r"""
 ██╗   ██╗ █████╗ ███╗   ███╗
 ██║   ██║██╔══██╗████╗ ████║
 ██║   ██║███████║██╔████╔██║
 ╚██╗ ██╔╝██╔══██║██║╚██╔╝██║
  ╚████╔╝ ██║  ██║██║ ╚═╝ ██║
   ╚═══╝  ╚═╝  ╚═╝╚═╝     ╚═╝
"""

SUBTITLE = "Valorant Account Manager"


def get_logo() -> Panel:
    """Get the full branded logo panel."""
    logo_text = Text()
    
    for line in LOGO_ART.strip().split("\n"):
        logo_text.append(line + "\n", style="bold #FF4655")
    
    logo_text.append(f"\n{SUBTITLE}\n", style="bold #ECE8E1")
    logo_text.append(f"v{APP_VERSION}", style="#768079")
    logo_text.append("  │  ", style="#768079")
    logo_text.append(f"Developer: {APP_DEVELOPER}", style="#768079")
    logo_text.append("  │  ", style="#768079")
    logo_text.append(f"Powered By: {APP_POWERED_BY}", style="#768079")
    
    return Panel(
        Align.center(logo_text),
        border_style="#FF4655",
        padding=(1, 4),
    )


def get_mini_header() -> Panel:
    """Get a compact header for sub-screens."""
    header = Text()
    header.append("VAM", style="bold #FF4655")
    header.append(f" v{APP_VERSION}", style="#768079")
    header.append("  │  ", style="#3a3a3a")
    header.append("Valorant Account Manager", style="#ECE8E1")
    
    return Panel(
        Align.center(header),
        border_style="#FF4655",
        padding=(0, 2),
    )


def get_section_title(title: str, icon: str = "►") -> str:
    """Get a formatted section title."""
    return f"\n  [bold #FF4655]{icon}[/bold #FF4655] [bold #ECE8E1]{title}[/bold #ECE8E1]"


def get_setup_banner() -> Panel:
    """Get the setup wizard banner."""
    text = Text()
    text.append("⚙️  Setup Wizard\n\n", style="bold #FF4655")
    text.append("Welcome to VAM! Let's set up your environment.\n", style="#ECE8E1")
    text.append("This will only take a moment.", style="#768079")
    
    return Panel(
        Align.center(text),
        border_style="#FF4655",
        padding=(1, 4),
    )
