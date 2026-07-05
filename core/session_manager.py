"""
VAM - Session Manager
FWOTD (First Win of the Day) tracking and session logic.
"""

from datetime import datetime, timedelta
from core.data_store import DataStore
from config.settings import FWOTD_COOLDOWN_HOURS, RANKED_READY_LEVEL, DOUBLE_GAME_LEVEL


class SessionManager:
    """Manages FWOTD tracking and game session logic."""
    
    def __init__(self, data_store: DataStore):
        self.store = data_store
    
    def is_fwotd_available(self, account: dict) -> bool:
        """Check if FWOTD is available for an account."""
        last_fwotd = account.get("last_fwotd")
        
        if not last_fwotd:
            return True
        
        try:
            last_time = datetime.fromisoformat(last_fwotd)
            next_time = last_time + timedelta(hours=FWOTD_COOLDOWN_HOURS)
            return datetime.now() >= next_time
        except (ValueError, TypeError):
            return True
    
    def get_time_until_fwotd(self, account: dict) -> timedelta | None:
        """Get remaining time until FWOTD is available. Returns None if already available."""
        last_fwotd = account.get("last_fwotd")
        
        if not last_fwotd:
            return None
        
        try:
            last_time = datetime.fromisoformat(last_fwotd)
            next_time = last_time + timedelta(hours=FWOTD_COOLDOWN_HOURS)
            now = datetime.now()
            
            if now >= next_time:
                return None
            return next_time - now
        except (ValueError, TypeError):
            return None
    
    def mark_fwotd_done(self, account_index: int) -> bool:
        """Mark FWOTD as completed for an account."""
        return self.store.update_account(account_index, {
            "last_fwotd": datetime.now().isoformat(),
            "fwotd_available": False,
        })
    
    def get_fwotd_ready_accounts(self) -> list[tuple[int, dict]]:
        """Get all accounts that have FWOTD available. Returns list of (index, account)."""
        accounts = self.store.load_accounts()
        ready = []
        
        for i, acc in enumerate(accounts):
            if acc.get("status") != "ranked_ready" and self.is_fwotd_available(acc):
                ready.append((i, acc))
        
        return ready
    
    def get_games_needed(self, account: dict) -> int:
        """Calculate total games needed to reach ranked ready."""
        level = account.get("level", 0)
        
        if level >= RANKED_READY_LEVEL:
            return 0
        
        if level >= DOUBLE_GAME_LEVEL:
            # After level 15, each level needs 2 wins
            return (RANKED_READY_LEVEL - level) * 2
        else:
            # Before level 15: 1 win per level up to 15, then 2 wins per level
            single_games = DOUBLE_GAME_LEVEL - level
            double_games = (RANKED_READY_LEVEL - DOUBLE_GAME_LEVEL) * 2
            return single_games + double_games
    
    def get_estimated_days(self, account: dict) -> int:
        """Estimate days to reach ranked ready (assuming 1 FWOTD per day)."""
        level = account.get("level", 0)
        
        if level >= RANKED_READY_LEVEL:
            return 0
        
        # Each FWOTD grants 1 level (simplification)
        # After level 15, need 2 games per level but FWOTD still gives 1 per day
        remaining_levels = RANKED_READY_LEVEL - level
        return remaining_levels  # ~1 level per day with FWOTD
    
    def get_priority_sorted_accounts(self) -> list[dict]:
        """
        Get accounts sorted by priority:
        1. FWOTD available first
        2. Then by level (lower first - need more work)
        3. Exclude ranked_ready accounts
        """
        accounts = self.store.load_accounts()
        
        def sort_key(acc):
            is_ready = self.is_fwotd_available(acc)
            is_ranked = acc.get("status") == "ranked_ready"
            level = acc.get("level", 0)
            
            # Ranked ready goes last
            if is_ranked:
                return (2, 0, level)
            # FWOTD ready goes first
            if is_ready:
                return (0, level, 0)
            # Not ready
            return (1, level, 0)
        
        return sorted(accounts, key=sort_key)
