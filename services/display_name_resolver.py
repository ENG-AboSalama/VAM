"""
VAM - Display Name Resolver
Resolves in-game display names via the Riot Client local API.
"""

import time
import logging
import requests
import urllib3
from config.settings import RIOT_LOCKFILE_PATH
from services.riot_client import RiotClient
from ui.console import console, print_status

# Suppress SSL warnings for self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup logging
logger = logging.getLogger(__name__)


class DisplayNameResolver:
    """
    Resolves the currently logged-in account's display name
    using the Riot Client's local API.
    
    Flow:
    1. Read lockfile to get port + auth credentials
    2. Query local API endpoint: /chat/v1/me
    3. Extract game_name and game_tag
    """
    
    def __init__(self, riot_client: RiotClient):
        self.riot_client = riot_client
    
    def _get_local_api_auth(self) -> tuple[str, tuple[str, str]] | None:
        """
        Read lockfile and return (base_url, auth_tuple).
        Returns None if lockfile not available.
        """
        lockfile = self.riot_client.read_lockfile()
        if not lockfile:
            return None
        
        port = lockfile["port"]
        password = lockfile["password"]
        base_url = f"https://127.0.0.1:{port}"
        auth = ("riot", password)
        
        return base_url, auth
    
    def resolve_display_name(self, max_retries: int = 3, retry_delay: int = 5) -> dict | None:
        """
        Get the display name of the currently logged-in account.
        
        Returns dict with:
            - game_name: Display name
            - game_tag: Display tag
            - puuid: Player UUID
        
        Or None if resolution fails.
        """
        for attempt in range(max_retries):
            api_info = self._get_local_api_auth()
            
            if not api_info:
                if attempt < max_retries - 1:
                    logger.debug(f"Lockfile not found. Retrying ({attempt + 1}/{max_retries})")
                    print_status(
                        f"Lockfile not found. Retrying in {retry_delay}s... ({attempt + 1}/{max_retries})",
                        "wait",
                    )
                    time.sleep(retry_delay)
                    continue
                logger.error("Lockfile not found after all retries")
                return None
            
            base_url, auth = api_info
            
            try:
                # Try /chat/v1/me endpoint (most reliable for game_name + game_tag)
                response = requests.get(
                    f"{base_url}/chat/v1/me",
                    auth=auth,
                    verify=False,  # Self-signed cert
                    timeout=10,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    game_name = data.get("game_name", "") or data.get("gameName", "")
                    game_tag = data.get("game_tag", "") or data.get("gameTag", "")
                    puuid = data.get("puuid", "")
                    
                    # Validate data
                    if not isinstance(game_name, str):
                        game_name = str(game_name) if game_name else ""
                    if not isinstance(game_tag, str):
                        game_tag = str(game_tag) if game_tag else ""
                    
                    if game_name and game_tag:
                        logger.info(f"Display name resolved: {game_name}#{game_tag}")
                        return {
                            "game_name": game_name,
                            "game_tag": game_tag,
                            "puuid": puuid,
                        }
                
                # Fallback: try /riot-client-auth/v1/userinfo endpoint
                response2 = requests.get(
                    f"{base_url}/riot-client-auth/v1/userinfo",
                    auth=auth,
                    verify=False,
                    timeout=10,
                )
                
                if response2.status_code == 200:
                    data2 = response2.json()
                    acct = data2.get("acct", {})
                    game_name = acct.get("game_name", "") or acct.get("gameName", "")
                    game_tag = acct.get("tag_line", "") or acct.get("gameTag", "")
                    
                    # Validate data
                    if not isinstance(game_name, str):
                        game_name = str(game_name) if game_name else ""
                    if not isinstance(game_tag, str):
                        game_tag = str(game_tag) if game_tag else ""
                    
                    if game_name and game_tag:
                        return {
                            "game_name": game_name,
                            "game_tag": game_tag,
                            "puuid": data2.get("sub", ""),
                        }
                    logger.debug(f"Incomplete data from /riot-client-auth/v1/userinfo: name={game_name}, tag={game_tag}")
                
                logger.debug(f"Both endpoints failed or returned incomplete data")
            
            except requests.exceptions.ConnectionError as e:
                logger.debug(f"Connection error: {e}")
                if attempt < max_retries - 1:
                    print_status(
                        f"Cannot connect to local API. Retrying in {retry_delay}s...",
                        "wait",
                    )
                    time.sleep(retry_delay)
                    continue
            except requests.exceptions.Timeout as e:
                logger.warning(f"Local API timeout: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
            except Exception as e:
                logger.error(f"Local API error: {e}")
                print_status(f"Local API error: {e}", "error")
        
        logger.debug("Failed to resolve display name after all attempts")
        return None
    
    def wait_and_resolve(self, timeout: int = 60) -> dict | None:
        """
        Wait for the user to be logged in, then resolve display name.
        Polls every few seconds until timeout.
        """
        logger.debug(f"Waiting for login (timeout: {timeout}s)")
        print_status("Waiting for login to complete...", "wait")
        
        start = time.time()
        while time.time() - start < timeout:
            result = self.resolve_display_name(max_retries=1)
            if result:
                return result
            time.sleep(3)
        
        logger.error(f"Timeout waiting for login after {timeout}s")
        return None

    def resolve_account_level(self) -> int | None:
        """
        Get the account level of the currently logged-in account
        using the Riot Client local API.
        
        Tries multiple endpoints to find the level:
        1. /chat/v1/me (often has account level data)
        2. /player-account/aliases/v1/active
        """
        api_info = self._get_local_api_auth()
        if not api_info:
            logger.warning("Cannot get local API auth for level resolution")
            return None
        
        base_url, auth = api_info
        
        try:
            # Try /chat/v1/me first — has "lol" field with account data
            logger.debug("Fetching account level from /chat/v1/me")
            response = requests.get(
                f"{base_url}/chat/v1/me",
                auth=auth,
                verify=False,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                # Some versions include account level in lol/acct data
                level = data.get("account_level") or data.get("lol", {}).get("level")
                if level:
                    try:
                        level_int = int(level)
                        return level_int
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid level value: {level}")
        except Exception as e:
            logger.debug(f"Error fetching account level: {e}")
