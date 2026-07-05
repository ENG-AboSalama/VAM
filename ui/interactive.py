"""
VAM - Interactive Menu Engine
Handles keyboard navigation (Arrows/WASD) for menus.
"""

import sys
import msvcrt
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from ui.console import console, clear_screen, print_header
from ui.banners import get_section_title

def get_key() -> str | None:
    """Read a single keypress from the console using native Unicode reader."""
    try:
        char = msvcrt.getwch()
        if char in ('\x00', '\xe0'):
            # Arrow keys return a 2-character sequence
            char = msvcrt.getwch()
            if char == 'H': return 'up'
            if char == 'P': return 'down'
            if char == 'K': return 'left'
            if char == 'M': return 'right'
        elif char == '\r': 
            return 'enter'
        elif char == '\x03': # Ctrl+C
            sys.exit(0)
        else:
            try:
                decoded = char.lower()
                # Map both English and Arabic QWERTY layouts
                if decoded in ('w', 'ص'): return 'up'
                if decoded in ('s', 'س'): return 'down'
                if decoded in ('a', 'ش'): return 'left'
                if decoded in ('d', 'ي'): return 'right'
            except Exception:
                pass
    except Exception:
        pass
    return None

def show_interactive_menu(
    title: str,
    options: list[tuple[str, str, str, str]], 
    icon: str = "🎮"
) -> str:
    """
    Shows an interactive menu.
    options format: [(return_value, icon, title, description)]
    """
    selected_idx = 0
    
    while True:
        clear_screen()
        print_header()
        if title and title != "Main Menu":
            console.print(get_section_title(title, icon))
        else:
            console.print()
            
        menu = Text()
        menu.append("\n")
        
        for i, (ret_val, opt_icon, opt_title, opt_desc) in enumerate(options):
            if i == selected_idx:
                # Highlighted state (Valorant Red)
                menu.append(f"  ❯ ", style="bold #FF4655")
                menu.append(f"{opt_icon}  {opt_title:<25}", style="bold #ECE8E1")
                menu.append(f"\n", style="")
            else:
                # Dim state
                menu.append(f"    ", style="")
                menu.append(f"{opt_icon}  {opt_title:<25}", style="#768079")
                menu.append(f"\n", style="")
                
        # Append Description box at the bottom
        current_desc = options[selected_idx][3]
        if current_desc:
            menu.append("\n")
            menu.append(f"  {current_desc}", style="italic #FF4655")
            menu.append("\n")
            
        console.print(Panel(
            menu,
            title=f"[bold #FF4655]{title}[/bold #FF4655]" if title == "Main Menu" else None,
            border_style="#3a3a3a",
            padding=(0, 2),
        ))
        
        # Navigation hints
        console.print("  [#768079]Use [bold #ECE8E1]↑/↓[/] or [bold #ECE8E1]W/S[/] to navigate. Press [bold #ECE8E1]Enter[/] to select.[/]", justify="center")
        
        # Wait for input
        key = get_key()
        if key == 'up':
            selected_idx = (selected_idx - 1) % len(options)
        elif key == 'down':
            selected_idx = (selected_idx + 1) % len(options)
        elif key == 'enter':
            return options[selected_idx][0]
