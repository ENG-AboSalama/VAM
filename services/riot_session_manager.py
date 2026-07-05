"""
VAM - Riot Session Manager
Handles extraction and injection of Riot Client cookies for silent auto-login.
"""

import os
import yaml
import logging
import requests
import time

class RiotSessionManager:
    """Manages Riot Client session cookies via RiotGamesPrivateSettings.yaml."""
    
    def __init__(self):
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        self.settings_path = os.path.join(
            local_app_data, 
            "Riot Games", 
            "Riot Client", 
            "Data", 
            "RiotGamesPrivateSettings.yaml"
        )
    
    def _read_yaml(self) -> dict:
        """Read the RiotGamesPrivateSettings.yaml file."""
        if not os.path.exists(self.settings_path):
            return {}
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.error(f"Failed to read Riot settings YAML: {e}")
            return {}
            
    def _write_yaml(self, data: dict) -> bool:
        """Write to the RiotGamesPrivateSettings.yaml file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False)
            return True
        except Exception as e:
            logging.error(f"Failed to write Riot settings YAML: {e}")
            return False

    def clear_session(self) -> bool:
        """
        Clears the session cookies from the RiotGamesPrivateSettings.yaml file
        without deleting the entire file, preserving other Riot Client settings.
        """
        data = self._read_yaml()
        if not data:
            return True
            
        modified = False
        if "rso-authenticator" in data and isinstance(data["rso-authenticator"], dict):
            if "tdid" in data["rso-authenticator"]:
                del data["rso-authenticator"]["tdid"]
                modified = True
                
        if "riot-login" in data and isinstance(data["riot-login"], dict):
            persist = data["riot-login"].get("persist")
            if isinstance(persist, dict) and "session" in persist and isinstance(persist["session"], dict):
                if "cookies" in persist["session"]:
                    persist["session"]["cookies"] = []
                    modified = True
                    
        if modified:
            return self._write_yaml(data)
        return True

    def extract_cookies(self) -> dict:
        """
        Extract authentication cookies (tdid, ssid, clid, csid) from the YAML file.
        Returns a dictionary of cookie data.
        """
        data = self._read_yaml()
        cookies = {}
        
        # Extract tdid from rso-authenticator
        if data and "rso-authenticator" in data and isinstance(data["rso-authenticator"], dict):
            rso = data["rso-authenticator"]
            if "tdid" in rso:
                cookies["tdid"] = rso["tdid"]
                
        # Extract ssid, clid, csid from riot-login.persist.session.cookies list
        if data and "riot-login" in data and isinstance(data["riot-login"], dict):
            persist = data["riot-login"].get("persist")
            if isinstance(persist, dict) and "session" in persist and isinstance(persist["session"], dict):
                session_cookies = persist["session"].get("cookies")
                if isinstance(session_cookies, list):
                    for cookie_obj in session_cookies:
                        if isinstance(cookie_obj, dict) and "name" in cookie_obj:
                            name = cookie_obj["name"]
                            if name in ["ssid", "clid", "csid", "ccid", "asid"]:
                                cookies[name] = cookie_obj
                                
        return cookies

    def inject_cookies(self, cookies: dict) -> bool:
        """
        Inject provided cookies into the RiotGamesPrivateSettings.yaml file.
        """
        if not cookies:
            return False
            
        data = self._read_yaml()
        if not data:
            data = {}
        
        # 1. Inject tdid into rso-authenticator
        if "tdid" in cookies:
            if "rso-authenticator" not in data or not isinstance(data["rso-authenticator"], dict):
                data["rso-authenticator"] = {}
            data["rso-authenticator"]["tdid"] = cookies["tdid"]
            
        # 2. Inject other session cookies into riot-login.persist.session.cookies
        session_cookie_names = ["ssid", "clid", "csid", "ccid", "asid"]
        session_cookies_to_inject = [cookies[name] for name in session_cookie_names if name in cookies]
        
        if session_cookies_to_inject:
            if "riot-login" not in data or not isinstance(data["riot-login"], dict):
                data["riot-login"] = {}
                
            persist = data["riot-login"].get("persist")
            if not isinstance(persist, dict):
                data["riot-login"]["persist"] = {}
                persist = data["riot-login"]["persist"]
                
            if "session" not in persist or not isinstance(persist["session"], dict):
                persist["session"] = {}
                
            # If there's an existing list, update it. If not, create it.
            existing_cookies = persist["session"].get("cookies", [])
            if not isinstance(existing_cookies, list):
                existing_cookies = []
                
            # Update existing cookies or append new ones
            for new_cookie in session_cookies_to_inject:
                found = False
                for i, existing in enumerate(existing_cookies):
                    if isinstance(existing, dict) and existing.get("name") == new_cookie.get("name"):
                        existing_cookies[i] = new_cookie
                        found = True
                        break
                if not found:
                    existing_cookies.append(new_cookie)
                    
            persist["session"]["cookies"] = existing_cookies
            
        return self._write_yaml(data)

    def refresh_cookies(self, cookies: dict) -> dict | None:
        """
        Use the cookie-reauth endpoint to get a fresh session (up to 1 month validity).
        Returns the updated cookies dict if successful, or None if failed.
        """
        if not cookies:
            return None
            
        url = "https://auth.riotgames.com/authorize?redirect_uri=http%3A%2F%2Flocalhost%2Fredirect&client_id=riot-client&response_type=token%20id_token&nonce=1&scope=account%20openid"
        
        # Prepare cookie jar with just values for the request
        cookie_jar = {}
        for name, data in cookies.items():
            if isinstance(data, dict) and "value" in data:
                cookie_jar[name] = data["value"]
            else:
                cookie_jar[name] = data
                
        headers = {
            "User-Agent": "RiotClient/63.0.9.4909983.4789131 rso-auth (Windows;10;;Professional, x64)",
            "Accept": "application/json, text/plain, */*"
        }
        
        session = requests.Session()
        try:
            response = session.get(url, headers=headers, cookies=cookie_jar, allow_redirects=False, timeout=10)
        except requests.RequestException as e:
            logging.error(f"Failed to refresh cookies: {e}")
            return None
            
        # Success usually means a redirect to opt_in with access_token
        if response.status_code in [301, 302, 303]:
            loc = response.headers.get("Location", "")
            if "access_token=" in loc:
                logging.info("Successfully refreshed session cookies via auth.riotgames.com")
                
                # Update the existing cookies dictionary with the new values
                # Keep old cookies that aren't replaced (like tdid)
                updated_cookies = cookies.copy()
                for c in session.cookies:
                    # Keep the format consistent with how they are stored (dicts with "name", "value", etc.)
                    # If it was a simple string (unlikely based on extract_cookies), convert it.
                    if c.name in updated_cookies and isinstance(updated_cookies[c.name], dict):
                        updated_cookies[c.name]["value"] = c.value
                    else:
                        updated_cookies[c.name] = {
                            "name": c.name,
                            "value": c.value,
                            "domain": c.domain,
                            "path": c.path,
                            "secure": c.secure,
                            "hostOnly": not c.domain.startswith('.') if c.domain else True
                        }
                return updated_cookies
            else:
                logging.warning(f"Cookie refresh failed, unexpected redirect: {loc}")
                return None
        else:
            logging.warning(f"Cookie refresh failed, status code: {response.status_code}")
            return None
