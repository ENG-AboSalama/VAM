"""
VAM - HenrikDev API Integration
Fetches Valorant account data (level, display name, region) via HenrikDev API.
"""

import time
import logging
import requests
from config.settings import HENRIK_API_BASE_URL, HENRIK_API_RATE_LIMIT, HENRIK_API_RATE_WINDOW
from ui.console import console, print_status
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Setup logging
logger = logging.getLogger(__name__)


class HenrikAPI:
    """Client for the HenrikDev Valorant API (v2)."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = HENRIK_API_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.api_key,
            "User-Agent": "VAM/1.0 (Valorant Account Manager)",
            "Accept": "application/json",
        })
        
        # Rate limiting tracking
        self._request_timestamps = []
    
    def _wait_for_rate_limit(self):
        """Wait if we're approaching the rate limit."""
        now = time.time()
        
        # Remove timestamps older than the rate window
        self._request_timestamps = [
            ts for ts in self._request_timestamps 
            if now - ts < HENRIK_API_RATE_WINDOW
        ]
        
        # If at limit, wait until oldest request expires
        if len(self._request_timestamps) >= HENRIK_API_RATE_LIMIT:
            wait_time = HENRIK_API_RATE_WINDOW - (now - self._request_timestamps[0]) + 1
            if wait_time > 0:
                print_status(f"Rate limit reached. Waiting {wait_time:.0f}s...", "wait")
                time.sleep(wait_time)
                self._request_timestamps = []
        
        self._request_timestamps.append(time.time())
    
    def fetch_account(self, name: str, tag: str) -> dict | None:
        """
        Fetch account info from HenrikDev API (v4.5.0+).
        
        Endpoint: GET /valorant/v2/account/{name}/{tag}
        
        Returns dict with account data or None on error.
        Response fields:
            - puuid: Unique player ID
            - region: Account region (eu, na, ap, kr)
            - account_level: Current level
            - name: Display name
            - tag: Display tag
            - card: Player card info
            - last_update: Last data update timestamp
        """
        self._wait_for_rate_limit()
        
        # Validate input
        if not name or not tag:
            logger.warning(f"Invalid input: name='{name}', tag='{tag}'")
            return {"error": "invalid_input", "message": "Name and tag cannot be empty"}
        
        url = f"{self.base_url}/v2/account/{name}/{tag}"
        
        try:
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 200 and "data" in data:
                    return data["data"]
                logger.warning(f"Invalid response structure for {name}#{tag}")
                return None
            
            elif response.status_code == 404:
                # Account not found OR hasn't played a game recently
                try:
                    data = response.json()
                    if "errors" in data and len(data["errors"]) > 0:
                        msg = data["errors"][0].get("message", "Not found")
                        logger.info(f"Account not found: {name}#{tag} - {msg}")
                        return {"error": "not_found", "message": msg}
                except Exception as e:
                    logger.warning(f"Could not parse 404 response: {e}")
                msg = f"Account '{name}#{tag}' not found (or needs to play 1 game)."
                logger.info(msg)
                return {"error": "not_found", "message": msg}
            
            elif response.status_code == 429:
                # Rate limited - return to caller to handle wait
                retry_after = int(response.headers.get("Retry-After", 60))
                return {"error": "rate_limited", "retry_after": retry_after, "message": f"Rate limited. Wait {retry_after}s."}
            
            elif response.status_code in (401, 403):
                logger.error(f"Invalid API key or access denied (status {response.status_code})")
                return {"error": "forbidden", "message": "Invalid API key or access denied."}
            
            else:
                logger.error(f"Unexpected API status {response.status_code} for {name}#{tag}")
                return {
                    "error": "api_error",
                    "message": f"API returned status {response.status_code}",
                }
        
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {name}#{tag}")
            return {"error": "timeout", "message": "Request timed out. Check your connection."}
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for {name}#{tag}")
            return {"error": "connection", "message": "Cannot connect to API. Check your internet."}
        except Exception as e:
            logger.error(f"Unexpected error fetching {name}#{tag}: {e}")
            return {"error": "request_error", "message": str(e)}
    
    def batch_refresh(self, accounts: list[dict], data_store) -> dict:
        """
        Refresh data for all accounts that have display names.
        
        Returns stats: {updated: int, failed: int, skipped: int, errors: list}
        """
        stats = {"updated": 0, "failed": 0, "skipped": 0, "errors": []}
        
        # Filter accounts that have display names (can be queried)
        queryable = [
            (i, acc) for i, acc in enumerate(accounts)
            if acc.get("display_name") and acc.get("tag")
        ]
        
        if not queryable:
            stats["skipped"] = len(accounts)
            logger.warning(f"No accounts with display names to refresh")
            return stats
        
        with Progress(
            SpinnerColumn(style="#FF4655"),
            TextColumn("[#ECE8E1]{task.description}"),
            BarColumn(bar_width=30, style="#3a3a3a", complete_style="#FF4655"),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Refreshing accounts...", total=len(queryable))
            
            for idx, acc in queryable:
                name = acc["display_name"]
                tag = acc["tag"]
                username = acc.get("username", "")  # Use username as identifier
                
                progress.update(task, description=f"Fetching {name}#{tag}...")
                
                # Fetch with retry logic for rate limiting
                retry = True
                while retry:
                    retry = False
                    result = self.fetch_account(name, tag)
                    
                    if result and result.get("error") == "rate_limited":
                        retry_after = result.get("retry_after", 60)
                        # Update progress bar safely without breaking the UI
                        progress.update(task, description=f"[bold #FF4655]Rate limited! Waiting {retry_after}s...[/]")
                        time.sleep(retry_after)
                        # Restore description and retry
                        progress.update(task, description=f"Retrying {name}#{tag}...")
                        retry = True
                
                if result and "error" not in result:
                    # Success - update account
                    try:
                        # Validate and convert account_level to int
                        api_level = result.get("account_level", acc.get("level", 0))
                        if api_level is None:
                            api_level = 0
                        try:
                            api_level = int(api_level)
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid level type for {name}#{tag}: {type(api_level)} = {api_level}")
                            api_level = 0
                        # Use the level directly as returned by the API
                        final_level = api_level
                        
                        # Extract other fields with validation
                        region = str(result.get("region", acc.get("region", ""))).lower()
                        puuid = str(result.get("puuid", acc.get("puuid", "")))
                        display_name = str(result.get("name", name))
                        display_tag = str(result.get("tag", tag))
                        
                        # Update account using the current index
                        # Note: We reload accounts to ensure we have fresh indices
                        current_accounts = data_store.load_accounts()
                        
                        # Find the account by username to get the current index
                        current_idx = None
                        for i, curr_acc in enumerate(current_accounts):
                            if curr_acc.get("username", "") == username:
                                current_idx = i
                                break
                        
                        if current_idx is not None:
                            success = data_store.update_account(current_idx, {
                                "level": final_level,
                                "region": region,
                                "puuid": puuid,
                                "display_name": display_name,
                                "tag": display_tag,
                            })
                            
                            if success:
                                stats["updated"] += 1
                            else:
                                logger.error(f"Save failed: {name}#{tag}")
                                stats["errors"].append(f"{name}#{tag}")
                                stats["failed"] += 1
                        else:
                            logger.error(f"Account not found in DB: {username}")
                            stats["errors"].append(f"{name}#{tag}")
                            stats["failed"] += 1
                    
                    except Exception as e:
                        logger.error(f"Error processing {name}#{tag}: {type(e).__name__}")
                        stats["errors"].append(f"{name}#{tag}")
                        stats["failed"] += 1
                
                elif result and result.get("error") == "not_found":
                    logger.warning(f"Not found: {name}#{tag}")
                    stats["errors"].append(f"{name}#{tag}")
                    stats["failed"] += 1
                
                else:
                    logger.error(f"Failed to fetch {name}#{tag}")
                    stats["errors"].append(f"{name}#{tag}")
                    stats["failed"] += 1
                
                progress.advance(task)
        
        stats["skipped"] = len(accounts) - len(queryable)
        logger.info(f"Refresh: {stats['updated']} OK | {stats['failed']} failed | {stats['skipped']} skipped")
        return stats
    
    def validate_api_key(self) -> bool:
        """Test if the API key is valid by making a simple request."""
        try:
            # Use a known account to test (Riot's official account)
            url = f"{self.base_url}/v2/account/Riot Games/000"
            response = self.session.get(url, timeout=10)
            
            # 401/403 = invalid key, anything else (including 404) = key works
            is_valid = response.status_code not in (401, 403)
            if is_valid:
                logger.info("API key validation successful")
            else:
                logger.error(f"API key validation failed: status {response.status_code}")
            return is_valid
        except requests.exceptions.RequestException as e:
            logger.error(f"API key validation error: {e}")
            return False
