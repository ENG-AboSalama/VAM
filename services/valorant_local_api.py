"""
VAM - Valorant Local PVP API Client
Fetches Level, XP, and FWOTD data directly from the Valorant PVP API
using tokens obtained from the running Riot Client local API.

Endpoint: GET https://pd.{shard}.a.pvp.net/account-xp/v1/players/{puuid}
Headers required:
    - Authorization: Bearer {access_token}
    - X-Riot-Entitlements-JWT: {entitlements_token}
    - X-Riot-ClientVersion: {client_version}
    - X-Riot-ClientPlatform: {client_platform_b64}

All tokens are extracted from the locally-running Riot Client.
"""

import time
import base64
import json
import logging
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
# Base64-encoded client platform string (PC / Windows)
CLIENT_PLATFORM_B64 = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0K"
    "CSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxh"
    "dGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
)

# Region → Shard mapping (official Riot routing)
REGION_TO_SHARD = {
    "na":    "na",
    "latam": "na",
    "br":    "na",
    "eu":    "eu",
    "ap":    "ap",
    "kr":    "kr",
    "pbe":   "pbe",
}

# The FWOTD source ID in the XPSources array is "first-win-of-the-day".
# As a safety fallback we also check if any single source contributed >= 900 AP
# (the FWOTD bonus is 1,000 AP; normal per-round AP is much lower).
FWOTD_SOURCE_ID = "first-win-of-the-day"
FWOTD_XP_MIN = 900  # Minimum AP from a single source to treat it as FWOTD

# Each Valorant account level requires exactly 5,000 AP
AP_PER_LEVEL = 5000


class ValorantLocalAPI:
    """
    Fetches Valorant account data directly from the PVP API using
    tokens extracted from the local Riot Client.

    Requires the Riot Client to be running and authenticated.
    """

    def __init__(self, riot_client):
        """
        Args:
            riot_client: RiotClient instance (used to read the lockfile).
        """
        self.riot_client = riot_client

    # ── Internal helpers ───────────────────────────────────────

    def _get_local_auth(self) -> tuple[str, tuple[str, str]] | None:
        """Return (base_url, basic_auth) from lockfile, or None."""
        lockfile = self.riot_client.read_lockfile()
        if not lockfile:
            return None
        port = lockfile["port"]
        password = lockfile["password"]
        return f"https://127.0.0.1:{port}", ("riot", password)

    def _get_access_token_and_entitlements(self) -> tuple[str, str] | None:
        """
        Fetch the bearer access token and entitlements JWT from the
        local Riot Client API.

        Returns (access_token, entitlements_token) or None on failure.
        """
        auth_info = self._get_local_auth()
        if not auth_info:
            logger.warning("Lockfile unavailable – cannot get access token.")
            return None

        base_url, auth = auth_info

        try:
            # 1. Get access token from /entitlements/v1/token
            resp = requests.get(
                f"{base_url}/entitlements/v1/token",
                auth=auth,
                verify=False,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"Entitlements endpoint returned {resp.status_code}")
                return None

            token_data = resp.json()
            access_token = token_data.get("accessToken", "")
            entitlements_token = token_data.get("token", "")

            if not access_token or not entitlements_token:
                logger.warning("Missing accessToken or entitlement token in response")
                return None

            return access_token, entitlements_token

        except Exception as e:
            logger.debug(f"Error fetching tokens: {e}")
            return None

    def _get_client_version(self) -> str:
        """
        Try to get the current Valorant client version from the local
        sessions endpoint. Falls back to a static placeholder.
        """
        auth_info = self._get_local_auth()
        if not auth_info:
            return "release-09.12-shipping-21-2549897"

        base_url, auth = auth_info
        try:
            resp = requests.get(
                f"{base_url}/product-session/v1/external-sessions",
                auth=auth,
                verify=False,
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                for session in data.values():
                    version = session.get("version", "")
                    if version:
                        # Format: "release-XX.YY-shipping-ZZ-XXXXXXX"
                        return version
        except Exception:
            pass

        return "release-09.12-shipping-21-2549897"

    def _get_puuid_and_region(self) -> tuple[str, str] | None:
        """
        Get PUUID and region from the local Riot Client API.
        Returns (puuid, region) or None.
        """
        auth_info = self._get_local_auth()
        if not auth_info:
            return None

        base_url, auth = auth_info
        try:
            # /riot-client-auth/v1/userinfo has sub (puuid) and acct
            resp = requests.get(
                f"{base_url}/riot-client-auth/v1/userinfo",
                auth=auth,
                verify=False,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                puuid = data.get("sub", "")
                # Try to get region from entitlements token or geolocation
                # For now return puuid only; region will be passed in from stored account
                if puuid:
                    return puuid, ""
        except Exception as e:
            logger.debug(f"Error fetching userinfo: {e}")

        return None

    # ── Public API ─────────────────────────────────────────────

    def fetch_account_xp(self, puuid: str, region: str) -> dict | None:
        """
        Fetch the raw account-xp response from the Valorant PVP API.

        Args:
            puuid:  Player UUID
            region: Account region (eu, na, ap, kr, latam, br, pbe)

        Returns dict with the API response, or None on failure.
        """
        shard = REGION_TO_SHARD.get(region.lower(), "eu")
        url = f"https://pd.{shard}.a.pvp.net/account-xp/v1/players/{puuid}"

        tokens = self._get_access_token_and_entitlements()
        if not tokens:
            logger.warning("Cannot fetch XP – no auth tokens available.")
            return None

        access_token, entitlements_token = tokens
        client_version = self._get_client_version()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Riot-Entitlements-JWT": entitlements_token,
            "X-Riot-ClientVersion": client_version,
            "X-Riot-ClientPlatform": CLIENT_PLATFORM_B64,
        }

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(f"account-xp API returned {resp.status_code} for {puuid}")
                return None
        except Exception as e:
            logger.debug(f"account-xp request error: {e}")
            return None

    def get_level_and_fwotd(
        self,
        puuid: str,
        region: str,
        max_wait: int = 30,
    ) -> dict | None:
        """
        High-level helper: fetch level and detect today's FWOTD completion.

        Polls up to `max_wait` seconds waiting for tokens to be available
        (useful right after a fresh login when the client is still loading).

        Returns:
            {
                "level": int,           # Current account level
                "xp": int,              # Current XP in level
                "fwotd_done": bool,     # True if FWOTD completed today
                "fwotd_xp": int,        # XP gained from FWOTD (0 if not done)
            }
            or None on failure.
        """
        from ui.console import print_status

        data = None
        deadline = time.time() + max_wait
        while time.time() < deadline:
            data = self.fetch_account_xp(puuid, region)
            if data is not None:
                break
            time.sleep(3)

        if data is None:
            logger.warning(f"Could not fetch account-xp for {puuid}")
            return None

        try:
            progress = data.get("Progress", {})
            level = int(progress.get("Level", 0))
            xp    = int(progress.get("XP", 0))

            # Detect FWOTD: look at today's history entries for a large XP spike
            history = data.get("History", [])
            fwotd_done = False
            fwotd_xp   = 0

            import datetime
            today_str = datetime.date.today().isoformat()  # "YYYY-MM-DD"

            for entry in history:
                # Entry format: {"ID": "...", "MatchStart": "YYYY-MM-DDTHH:MM:SS...",
                #                "StartProgress": {...}, "EndProgress": {...},
                #                "XPDelta": int,
                #                "XPSources": [{"ID": "time-played", "Amount": N},
                #                              {"ID": "first-win-of-the-day", "Amount": N}, ...]}
                match_start = entry.get("MatchStart", "")
                if not match_start.startswith(today_str):
                    continue  # Not today

                # XPSources is a LIST of {"ID": str, "Amount": int} objects
                xp_sources = entry.get("XPSources", []) or []
                for source in xp_sources:
                    source_id = str(source.get("ID", "")).lower()
                    amount    = int(source.get("Amount", 0))
                    if source_id == FWOTD_SOURCE_ID or amount >= FWOTD_XP_MIN:
                        fwotd_done = True
                        fwotd_xp   = amount
                        break

                if fwotd_done:
                    break

            return {
                "level": level,
                "xp": xp,
                "xp_to_next": max(0, AP_PER_LEVEL - xp),  # AP remaining until next level
                "fwotd_done": fwotd_done,
                "fwotd_xp": fwotd_xp,
            }

        except Exception as e:
            logger.error(f"Error parsing account-xp response: {e}")
            return None

    def wait_for_local_api(self, timeout: int = 30) -> bool:
        """
        Wait until the local Riot Client API is reachable (lockfile exists
        and returns a valid response). Used after a fresh login.

        Returns True when ready, False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            auth_info = self._get_local_auth()
            if auth_info:
                base_url, auth = auth_info
                try:
                    resp = requests.get(
                        f"{base_url}/riot-client-auth/v1/userinfo",
                        auth=auth,
                        verify=False,
                        timeout=3,
                    )
                    if resp.status_code == 200:
                        return True
                except Exception:
                    pass
            time.sleep(2)
        return False
