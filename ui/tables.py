"""
VAM - Account Tables
Rich tables for displaying account information.
"""

from rich.table import Table
from rich.text import Text
from rich.progress_bar import ProgressBar
from rich.panel import Panel
from rich.align import Align
from rich.console import Group
from datetime import datetime, timedelta
from config.settings import (
    COLORS, RANKED_READY_LEVEL, DOUBLE_GAME_LEVEL,
    FWOTD_COOLDOWN_HOURS, AccountStatus
)

# Background color for the "unfilled" part of any progress bar. Bars are
# drawn with plain space characters carrying this as a *background*
# color, instead of a "░" block glyph. A space always renders — there's
# no glyph that a font can be missing — so the empty portion of the bar
# is guaranteed to show up as a solid, visible track instead of vanishing
# the way "░" was doing.
_TRACK_BG = "#3a3a3a"


def _get_level_style(level: int) -> str:
    """Get color style based on account level."""
    if level >= RANKED_READY_LEVEL:
        return COLORS["level_ready"]
    elif level >= DOUBLE_GAME_LEVEL:
        return COLORS["level_high"]
    elif level >= 6:
        return COLORS["level_mid"]
    else:
        return COLORS["level_low"]


def _get_status_display(status: str) -> Text:
    """Get styled status text."""
    status_map = {
        AccountStatus.NEW: ("NEW", "bold #3498DB"),
        AccountStatus.IN_PROGRESS: ("IN PROGRESS", f"bold {COLORS['warning']}"),
        AccountStatus.RANKED_READY: ("RANKED READY", f"bold {COLORS['level_ready']}"),
        AccountStatus.ERROR: ("ERROR", f"bold {COLORS['error']}"),
    }
    label, style = status_map.get(status, ("UNKNOWN", "muted"))
    return Text(label, style=style)


def _get_fwotd_display(account: dict) -> Text:
    """Get FWOTD availability display."""
    last_fwotd = account.get("last_fwotd")

    if not last_fwotd:
        return Text("● READY", style=f"bold {COLORS['success']}")

    try:
        last_time = datetime.fromisoformat(last_fwotd)
        next_time = last_time + timedelta(hours=FWOTD_COOLDOWN_HOURS)
        now = datetime.now()

        if now >= next_time:
            return Text("● READY", style=f"bold {COLORS['success']}")

        remaining = next_time - now
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)

        if hours < 2:
            return Text(f"● {hours}h {minutes}m", style=f"bold {COLORS['warning']}")
        else:
            return Text(f"○ {hours}h {minutes}m", style=f"{COLORS['error']}")
    except (ValueError, TypeError):
        return Text("● READY", style=f"bold {COLORS['success']}")


# ---------------------------------------------------------------------------
# Level + progress rendering
#
# Design:
#   - The bar's "track" (empty part) is a background-colored space, not a
#     Unicode glyph, so it always renders — fixing the disappearing "░".
#   - Level number + AP progress are merged into ONE "Level" column as a
#     two-line cell (level on line 1, progress on line 2) instead of two
#     separate columns, so related info stays grouped per account without
#     a second column stretching out with empty space.
# ---------------------------------------------------------------------------

def _render_bar(pct: float, fill_color: str, width: int = 12) -> Text:
    """Render a solid two-tone progress bar (filled portion + track)."""
    pct = max(0.0, min(1.0, pct))
    filled = round(pct * width)
    empty = width - filled

    bar = Text()
    if filled:
        bar.append(" " * filled, style=f"on {fill_color}")
    if empty:
        bar.append(" " * empty, style=f"on {_TRACK_BG}")
    return bar


def _get_level_display(level: int) -> Text:
    """Compact, tier-colored 'what level is this account' display."""
    color = _get_level_style(level)
    text = Text()

    if level >= RANKED_READY_LEVEL:
        text.append("✓ ", style=f"bold {color}")
    text.append(f"Lv.{level:02d}", style=f"bold {color}")
    text.append(f"/{RANKED_READY_LEVEL}", style="#5a5a5a")
    return text


def _get_ap_progress_line(level: int, xp: int | float | None, width: int = 12) -> Text:
    """Single-line 'AP left to next level': bar + percentage + AP remaining."""
    color = _get_level_style(level)

    if level >= RANKED_READY_LEVEL:
        return Text("Ranked Ready", style=f"bold {color}")

    if xp is None or not isinstance(xp, (int, float)) or xp < 0:
        # No bar at all here on purpose: a bar implies real data, and we
        # don't want an untouched/empty bar to look identical to a
        # genuine "0% progress" account.
        return Text("no XP data yet", style="#5a5a5a")

    xp_int = int(xp)
    pct = min(1.0, xp_int / 5000)
    remaining = max(0, 5000 - xp_int)
    remaining_str = f"{remaining/1000:.1f}k" if remaining >= 1000 else str(remaining)

    line = Text()
    line.append_text(_render_bar(pct, color, width))
    line.append(f" {int(pct * 100):3d}%", style=f"bold {color}")
    line.append(f"  {remaining_str} AP left", style="#768079")
    return line


def _get_level_cell(level: int, xp: int | float | None, width: int = 8) -> Text:
    """Single-line Level cell: level number + bar + AP left, all in one row.

    No separate "%" number here — the bar's fill already communicates the
    fraction visually, so printing the percentage next to it is redundant
    and just adds width for no extra clarity. Spacing is kept tight (single
    spaces, a short bar) so the whole thing reliably fits on one line and
    never wraps inside the column — a wrap here is what caused the "left"
    on its own line before.
    """
    cell = _get_level_display(level)
    cell.append(" ")

    color = _get_level_style(level)

    if level >= RANKED_READY_LEVEL:
        cell.append("Ranked Ready", style=f"bold {color}")
        return cell

    if xp is None or not isinstance(xp, (int, float)) or xp < 0:
        cell.append("no XP data", style="#5a5a5a")
        return cell

    xp_int = int(xp)
    pct = min(1.0, xp_int / 5000)
    remaining = max(0, 5000 - xp_int)
    remaining_str = f"{remaining/1000:.1f}k" if remaining >= 1000 else str(remaining)

    cell.append_text(_render_bar(pct, color, width))
    cell.append(f" {remaining_str} AP left", style="#768079")
    return cell


def build_accounts_table(accounts: list[dict], title: str = "Account Overview") -> Panel:
    """Build the main accounts table."""
    if not accounts:
        empty_text = Text()
        empty_text.append("\n  No accounts found.\n", style="#768079")
        empty_text.append("  Use 'Add Account' or 'Import Accounts' to get started.\n", style="#768079")
        return Panel(
            empty_text,
            title=f"[bold #FF4655]📋 {title}[/bold #FF4655]",
            border_style="#3a3a3a",
            padding=(1, 2),
        )

    table = Table(
        show_header=True,
        header_style="bold #FF4655",
        border_style="#3a3a3a",
        show_lines=False,
        pad_edge=True,
        expand=True,
    )

    table.add_column("#", style="#768079", width=4, justify="center")
    table.add_column("Display Name", style="bold #ECE8E1", min_width=20, ratio=1)
    table.add_column("Level", min_width=28, max_width=32)
    table.add_column("FWOTD", justify="center", min_width=12)
    table.add_column("Region", style="#768079", justify="center", width=8)

    for i, acc in enumerate(accounts, 1):
        display = acc.get("display_name", "")
        tag = acc.get("tag", "")
        display_full = f"{display}#{tag}" if display and tag else acc.get("username", "N/A")

        level = acc.get("level", 0)
        xp = acc.get("xp")  # None if not yet fetched via local API

        level_cell = _get_level_cell(level, xp)
        fwotd_text = _get_fwotd_display(acc)
        region = acc.get("region", "—").upper()

        table.add_row(
            str(i),
            display_full,
            level_cell,
            fwotd_text,
            region,
        )

    return Panel(
        table,
        title=f"[bold #FF4655]📋 {title}[/bold #FF4655]",
        border_style="#FF4655",
        padding=(1, 1),
    )


def build_account_detail(account: dict) -> Panel:
    """Build a detailed view of a single account."""
    display = account.get("display_name", "N/A")
    tag = account.get("tag", "")
    display_full = f"{display}#{tag}" if display and tag else "Not Resolved"

    level = account.get("level", 0)
    status = account.get("status", AccountStatus.NEW)
    region = account.get("region", "Unknown").upper()
    username = account.get("username", "N/A")

    # Calculate games needed
    if level >= RANKED_READY_LEVEL:
        games_needed = 0
    elif level >= DOUBLE_GAME_LEVEL:
        games_needed = (RANKED_READY_LEVEL - level) * 2
    else:
        games_left_single = max(0, DOUBLE_GAME_LEVEL - level)
        games_left_double = (RANKED_READY_LEVEL - DOUBLE_GAME_LEVEL) * 2
        games_needed = games_left_single + games_left_double

    detail = Text()
    detail.append(f"  Display Name:  ", style="#768079")
    detail.append(f"{display_full}\n", style="bold #ECE8E1")
    detail.append(f"  Username:      ", style="#768079")
    detail.append(f"{username}\n", style="#ECE8E1")
    detail.append(f"  Level:         ", style="#768079")
    detail.append_text(_get_level_display(level))
    detail.append("\n")

    # XP progress — only meaningful if xp data has been fetched (via local API)
    xp = account.get("xp")
    detail.append(f"  XP Progress:   ", style="#768079")
    detail.append_text(_get_ap_progress_line(level, xp, width=16))
    detail.append("\n")

    detail.append(f"  Status:        ", style="#768079")
    detail.append(f"{status.upper()}\n", style="bold")
    detail.append(f"  Region:        ", style="#768079")
    detail.append(f"{region}\n", style="#ECE8E1")
    detail.append(f"  FWOTD:         ", style="#768079")
    fwotd = _get_fwotd_display(account)
    detail.append_text(fwotd)
    detail.append(f"\n  Games Needed:  ", style="#768079")
    detail.append(f"{games_needed} wins", style="#ECE8E1" if games_needed > 0 else COLORS["level_ready"])

    return Panel(
        detail,
        title=f"[bold #FF4655]🎮 Account Details[/bold #FF4655]",
        border_style="#FF4655",
        padding=(1, 2),
    )


def build_summary_stats(accounts: list[dict]) -> Panel:
    """Build summary statistics panel."""
    total = len(accounts)
    ranked_ready = sum(1 for a in accounts if a.get("status") == AccountStatus.RANKED_READY)
    in_progress = sum(1 for a in accounts if a.get("status") == AccountStatus.IN_PROGRESS)
    new_accounts = sum(1 for a in accounts if a.get("status") == AccountStatus.NEW)

    fwotd_ready = 0
    for acc in accounts:
        last_fwotd = acc.get("last_fwotd")
        if not last_fwotd:
            fwotd_ready += 1
        else:
            try:
                last_time = datetime.fromisoformat(last_fwotd)
                if datetime.now() >= last_time + timedelta(hours=FWOTD_COOLDOWN_HOURS):
                    fwotd_ready += 1
            except (ValueError, TypeError):
                fwotd_ready += 1

    stats = Text()
    stats.append(f"  Total:         ", style="#768079")
    stats.append(f"{total}\n", style="bold #ECE8E1")
    stats.append(f"  Ranked Ready:  ", style="#768079")
    stats.append(f"{ranked_ready}\n", style=f"bold {COLORS['level_ready']}")
    stats.append(f"  In Progress:   ", style="#768079")
    stats.append(f"{in_progress}\n", style=f"bold {COLORS['warning']}")
    stats.append(f"  New:           ", style="#768079")
    stats.append(f"{new_accounts}\n", style=f"bold {COLORS['info']}")
    stats.append(f"  FWOTD Ready:   ", style="#768079")
    stats.append(f"{fwotd_ready}/{total}", style=f"bold {COLORS['success']}")

    return Panel(
        stats,
        title=f"[bold #FF4655]📊 Summary[/bold #FF4655]",
        border_style="#FF4655",
        padding=(1, 2),
    )


def build_suffering_dashboard(accounts: list[dict], session_mgr) -> Panel:
    """Build the Start Suffering dashboard table showing FWOTD status for all accounts."""
    if not accounts:
        empty_text = Text()
        empty_text.append("\n  No accounts found.\n", style="#768079")
        empty_text.append("  Add accounts first before starting.\n", style="#768079")
        return Panel(
            empty_text,
            title="[bold #FF4655]🔥 Start Suffering – FWOTD Queue[/bold #FF4655]",
            border_style="#FF4655",
            padding=(1, 2),
        )

    # Separate into ready and not-ready, preserving original indices
    ready = []
    not_ready = []
    for i, acc in enumerate(accounts):
        # Skip ranked_ready accounts
        if acc.get("status") == AccountStatus.RANKED_READY:
            continue
        if session_mgr.is_fwotd_available(acc):
            ready.append((i, acc))
        else:
            not_ready.append((i, acc))

    # Sort ready by level (lowest first – needs more work)
    ready.sort(key=lambda x: x[1].get("level", 0))
    # Sort not-ready by remaining time (shortest first)
    not_ready.sort(key=lambda x: (session_mgr.get_time_until_fwotd(x[1]) or timedelta(0)).total_seconds())

    table = Table(
        show_header=True,
        header_style="bold #FF4655",
        border_style="#3a3a3a",
        show_lines=False,
        pad_edge=True,
        expand=True,
    )

    table.add_column("#", style="#768079", width=4, justify="center")
    table.add_column("Account", style="bold #ECE8E1", min_width=22)
    table.add_column("Level", min_width=10, justify="center")
    table.add_column("FWOTD Status", min_width=16, justify="center")
    table.add_column("Queue", justify="center", min_width=12)

    row_num = 1

    # Ready accounts first
    for orig_idx, acc in ready:
        display = acc.get("display_name", "")
        tag = acc.get("tag", "")
        name = f"{display}#{tag}" if display and tag else acc.get("username", "N/A")
        level = acc.get("level", 0)

        level_text = Text(f"Lv.{level}", style=_get_level_style(level))
        fwotd_text = Text("✅ READY", style=f"bold {COLORS['success']}")
        queue_text = Text("▶ Queued", style=f"bold {COLORS['success']}")

        table.add_row(str(row_num), name, level_text, fwotd_text, queue_text)
        row_num += 1

    # Separator if both lists have items
    if ready and not_ready:
        table.add_row("", "", "", "", "", end_section=True)

    # Not-ready accounts
    for orig_idx, acc in not_ready:
        display = acc.get("display_name", "")
        tag = acc.get("tag", "")
        name = f"{display}#{tag}" if display and tag else acc.get("username", "N/A")
        level = acc.get("level", 0)

        level_text = Text(f"Lv.{level}", style=_get_level_style(level))

        remaining = session_mgr.get_time_until_fwotd(acc)
        if remaining:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            fwotd_text = Text(f"⏳ {hours}h {minutes}m", style=f"{COLORS['warning']}")
        else:
            fwotd_text = Text("✅ READY", style=f"bold {COLORS['success']}")

        queue_text = Text("⏸ Wait", style=f"{COLORS['muted']}")

        table.add_row(str(row_num), name, level_text, fwotd_text, queue_text)
        row_num += 1

    # Summary line
    total_shown = len(ready) + len(not_ready)
    ranked_count = sum(1 for a in accounts if a.get("status") == AccountStatus.RANKED_READY)

    summary = Text()
    summary.append(f"\n  Ready: ", style="#768079")
    summary.append(f"{len(ready)}", style=f"bold {COLORS['success']}")
    summary.append(f"/{total_shown}", style="#768079")
    summary.append(f" accounts", style="#768079")
    if ranked_count > 0:
        summary.append(f"  │  ", style="#3a3a3a")
        summary.append(f"{ranked_count} Ranked Ready (skipped)", style=f"{COLORS['level_ready']}")

    return Panel(
        Group(table, summary),
        title="[bold #FF4655]🔥 Start Suffering – FWOTD Queue[/bold #FF4655]",
        border_style="#FF4655",
        padding=(1, 1),
    )
