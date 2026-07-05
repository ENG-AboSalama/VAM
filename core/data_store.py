"""
VAM - Data Store
JSON-based data persistence for accounts and app configuration.
"""

import json
import os
import uuid
from datetime import datetime
from config.settings import (
    DATA_DIR, ACCOUNTS_FILE, CONFIG_FILE, 
    ensure_data_dirs, AccountStatus
)


class DataStore:
    """Handles reading and writing data to JSON files."""
    
    def __init__(self):
        ensure_data_dirs()
        self._accounts_cache = None
        self._accounts_mtime = 0
        self._config_cache = None
        self._config_mtime = 0
    
    # ─── Accounts ────────────────────────────────────────────
    
    def load_accounts(self) -> list[dict]:
        """Load all accounts from the JSON file."""
        if self._accounts_cache is not None:
            try:
                mtime = os.path.getmtime(ACCOUNTS_FILE)
                if mtime == self._accounts_mtime:
                    return self._accounts_cache
            except OSError:
                pass
        
        if not os.path.exists(ACCOUNTS_FILE):
            self._accounts_cache = []
            return self._accounts_cache
        
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._accounts_cache = data.get("accounts", [])
                try:
                    self._accounts_mtime = os.path.getmtime(ACCOUNTS_FILE)
                except OSError:
                    self._accounts_mtime = 0
                return self._accounts_cache
        except (json.JSONDecodeError, IOError):
            self._accounts_cache = []
            return self._accounts_cache
    
    def save_accounts(self, accounts: list[dict]) -> bool:
        """Save accounts to the JSON file."""
        try:
            ensure_data_dirs()
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump({"accounts": accounts}, f, indent=2, ensure_ascii=False)
            self._accounts_cache = accounts
            try:
                self._accounts_mtime = os.path.getmtime(ACCOUNTS_FILE)
            except OSError:
                self._accounts_mtime = 0
            return True
        except IOError:
            return False
    
    def add_account(self, username: str, password: str) -> bool:
        """Add a new account. Returns True if added, False if duplicate or save failed."""
        accounts = self.load_accounts()
        
        # Check for duplicate
        for acc in accounts:
            if acc["username"].lower() == username.lower():
                return False  # Duplicate
        
        account = {
            "id": str(uuid.uuid4()),
            "username": username,
            "password": password,
            "display_name": "",
            "tag": "",
            "level": 0,
            "region": "",
            "puuid": "",
            "status": AccountStatus.NEW,
            "last_fwotd": None,
            "fwotd_available": True,
            "added_date": datetime.now().isoformat(),
            "cookies": {},
        }
        
        accounts.append(account)
        return self.save_accounts(accounts)  # Return save result
    
    def remove_account(self, index: int) -> bool:
        """Remove an account by index."""
        accounts = self.load_accounts()
        if 0 <= index < len(accounts):
            accounts.pop(index)
            self.save_accounts(accounts)
            return True
        return False
    
    def update_account(self, index: int, updates: dict) -> bool:
        """Update an account's fields."""
        accounts = self.load_accounts()
        if 0 <= index < len(accounts):
            accounts[index].update(updates)
            # Auto-update status based on level
            level = accounts[index].get("level", 0)
            if level >= 20:
                accounts[index]["status"] = AccountStatus.RANKED_READY
            elif level > 0:
                accounts[index]["status"] = AccountStatus.IN_PROGRESS
            return self.save_accounts(accounts)  # Return save result, not just True
        return False
    
    def get_account_by_index(self, index: int) -> dict | None:
        """Get a single account by index."""
        accounts = self.load_accounts()
        if 0 <= index < len(accounts):
            return accounts[index]
        return None
    
    def import_accounts(self, lines: list[str]) -> tuple[int, int]:
        """
        Import accounts from lines of text.
        Supports formats: 'username:password' and 'username,password'
        Returns (added_count, skipped_count).
        """
        added = 0
        skipped = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Try splitting by : or ,
            parts = None
            if ":" in line:
                parts = line.split(":", 1)
            elif "," in line:
                parts = line.split(",", 1)
            
            if parts and len(parts) == 2:
                username, password = parts[0].strip(), parts[1].strip()
                if username and password:
                    result = self.add_account(username, password)
                    if result:
                        added += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        
        return added, skipped
    
    def export_ranked_ready(self) -> list[dict]:
        """Get all ranked-ready accounts."""
        accounts = self.load_accounts()
        return [a for a in accounts if a.get("status") == AccountStatus.RANKED_READY]
    
    def invalidate_cache(self):
        """Force reload from disk on next access."""
        self._accounts_cache = None
        self._accounts_mtime = 0
        self._config_cache = None
        self._config_mtime = 0
    
    # ─── App Config ──────────────────────────────────────────
    
    def load_config(self) -> dict:
        """Load app configuration."""
        if self._config_cache is not None:
            return self._config_cache
        
        if not os.path.exists(CONFIG_FILE):
            self._config_cache = {}
            return self._config_cache
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self._config_cache = json.load(f)
                return self._config_cache
        except (json.JSONDecodeError, IOError):
            self._config_cache = {}
            return self._config_cache
    
    def save_config(self, config: dict) -> bool:
        """Save app configuration."""
        try:
            ensure_data_dirs()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._config_cache = config
            return True
        except IOError:
            return False
    
    def is_setup_complete(self) -> bool:
        """Check if initial setup has been completed."""
        config = self.load_config()
        return config.get("setup_complete", False)
    
    def get_riot_client_path(self) -> str:
        """Get the configured Riot Client path."""
        config = self.load_config()
        return config.get("riot_client_path", "")
    
    def get_api_key(self) -> str:
        """Get the configured API key."""
        config = self.load_config()
        return config.get("api_key", "")
