r"""
HubcapDB API client, credential management, and file download handler.
Endpoints:
- User stats: GET https://hubcapmanifest.com/api/v1/user/stats
- Manifest:   GET https://hubcapmanifest.com/api/v1/manifest/{app_id}
- Depot keys: GET https://hubcapmanifest.com/api/v1/depot-keys
Target directory: Documents\GameManifests\<AppID>\
"""

import os
import io
import json
import zipfile
from typing import Optional, Dict, Any, Tuple
import requests
from PyQt6.QtCore import QSettings

HUBCAP_BASE_URL = "https://hubcapmanifest.com/api/v1"
API_KEYS_URL = "https://hubcapmanifest.com/api-keys"
SETTINGS_ORG = "SteamSearch"
SETTINGS_APP = "SteamGameSearch"
SETTINGS_KEY_NAME = "hubcap_api_key"

USER_AGENT = "SteamSearchDesktop/1.0 (Windows NT 10.0; Win64; x64)"


class HubcapAuthError(Exception):
    """Raised when Hubcap API returns 401 Unauthorized or expired key."""
    pass


class HubcapNotFoundError(Exception):
    """Raised when Hubcap API returns 404 Not Found (e.g. game manifest not cached)."""
    pass


class HubcapAPIError(Exception):
    """Raised when Hubcap API returns an unexpected error."""
    pass


def get_stored_api_key() -> str:
    """Retrieve stored API key from Windows QSettings (Registry)."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    key = settings.value(SETTINGS_KEY_NAME, "")
    return str(key).strip() if key else ""


def set_stored_api_key(api_key: str):
    """Save API key to Windows QSettings (Registry)."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(SETTINGS_KEY_NAME, api_key.strip())


def clear_stored_api_key():
    """Clear stored API key from Windows QSettings."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.remove(SETTINGS_KEY_NAME)


def get_game_documents_dir(app_id: int) -> str:
    r"""
    Get the target directory path: Documents\GameManifests\<AppID>\
    Does NOT create the directory; directory is only created when downloading.
    """
    documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(documents_dir, "GameManifests", str(app_id))


class HubcapClient:
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or get_stored_api_key()

    @property
    def api_key(self) -> str:
        return self._api_key or get_stored_api_key()

    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value.strip()

    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        key = self.api_key
        if not key:
            raise HubcapAuthError("No Hubcap API key configured.")
        return {
            "Authorization": f"Bearer {key}",
            "X-API-Key": key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/zip, */*",
        }

    def fetch_user_stats(self) -> Dict[str, Any]:
        """
        Query GET /api/v1/user/stats.
        Returns parsed stats dictionary.
        Raises HubcapAuthError if key is missing, invalid, or expired (401).
        """
        headers = self._get_headers()
        url = f"{HUBCAP_BASE_URL}/user/stats"

        try:
            resp = requests.get(url, headers=headers, timeout=8)
        except Exception as e:
            raise HubcapAPIError(f"Network error connecting to Hubcap: {e}")

        if resp.status_code == 401:
            raise HubcapAuthError("Hubcap API key is invalid or has expired (keys expire after 7 days).")
        
        if not resp.ok:
            raise HubcapAPIError(f"Hubcap API returned HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def download_manifest(self, app_id: int) -> requests.Response:
        """Query GET /api/v1/manifest/{app_id}."""
        headers = self._get_headers()
        url = f"{HUBCAP_BASE_URL}/manifest/{app_id}"

        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            raise HubcapAPIError(f"Network error downloading manifest: {e}")

        if resp.status_code == 401:
            raise HubcapAuthError("Hubcap API key is invalid or has expired (keys expire after 7 days).")
        
        if resp.status_code == 404:
            raise HubcapNotFoundError(f"Manifest for App ID {app_id} was not found on HubcapDB (HTTP 404).")

        if not resp.ok:
            raise HubcapAPIError(f"Hubcap manifest error (HTTP {resp.status_code}): {resp.text[:200]}")

        return resp

    def download_depot_keys(self) -> requests.Response:
        """Query GET /api/v1/depot-keys."""
        headers = self._get_headers()
        url = f"{HUBCAP_BASE_URL}/depot-keys"

        try:
            resp = requests.get(url, headers=headers, timeout=20)
        except Exception as e:
            raise HubcapAPIError(f"Network error downloading depot keys: {e}")

        if resp.status_code == 401:
            raise HubcapAuthError("Hubcap API key is invalid or has expired (keys expire after 7 days).")

        if not resp.ok:
            raise HubcapAPIError(f"Hubcap depot keys error (HTTP {resp.status_code}): {resp.text[:200]}")

        return resp

    def download_and_save(self, app_id: int, game_name: str) -> Tuple[str, int]:
        r"""
        Download both manifest files and depot keys, saving them to Documents\GameManifests\<AppID>\.
        Returns (target_directory, file_count).
        """
        target_dir = get_game_documents_dir(app_id)
        os.makedirs(target_dir, exist_ok=True)
        saved_files_count = 0

        # 1. Download manifest files
        manifest_resp = self.download_manifest(app_id)
        manifest_content = manifest_resp.content

        # Check if response is a ZIP file
        if manifest_content.startswith(b"PK"):
            try:
                with zipfile.ZipFile(io.BytesIO(manifest_content)) as zf:
                    zf.extractall(target_dir)
                    saved_files_count += len(zf.namelist())
            except Exception:
                # If extraction fails, save as zip file
                zip_path = os.path.join(target_dir, f"manifests_{app_id}.zip")
                with open(zip_path, "wb") as f:
                    f.write(manifest_content)
                saved_files_count += 1
        else:
            # Check if JSON or raw manifest text/binary
            try:
                manifest_json = manifest_resp.json()
                manifest_path = os.path.join(target_dir, f"manifest_{app_id}.json")
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest_json, f, indent=2)
                saved_files_count += 1
            except Exception:
                manifest_path = os.path.join(target_dir, f"{app_id}.manifest")
                with open(manifest_path, "wb") as f:
                    f.write(manifest_content)
                saved_files_count += 1

        # 2. Write metadata info file
        info_path = os.path.join(target_dir, "game_info.txt")
        with open(info_path, "w", encoding="utf-8") as f:
            f.write(f"Game: {game_name}\nApp ID: {app_id}\nDownloaded via HubcapDB\n")
        saved_files_count += 1

        return target_dir, saved_files_count


def extract_downloads_left(stats: Dict[str, Any]) -> str:
    """Extract and format remaining downloads from stats response."""
    if not isinstance(stats, dict):
        return "Active"

    # Inspect common field names in Hubcap API
    for key in ["downloads_left", "remaining_downloads", "downloads_remaining", "remaining", "downloads_today_left", "downloads"]:
        if key in stats and stats[key] is not None:
            val = stats[key]
            # If it has daily limit, e.g. limit or max
            limit = stats.get("daily_limit") or stats.get("max_downloads") or stats.get("limit")
            if limit:
                return f"{val}/{limit} downloads left"
            return f"{val} downloads left"

    # Fallback to scanning dictionary
    for k, v in stats.items():
        if "download" in k.lower() and isinstance(v, (int, str)):
            return f"{v} downloads left"

    return "Connected"


from PyQt6.QtCore import QThread, pyqtSignal


class UserStatsWorker(QThread):
    """Worker thread to fetch user stats without blocking GUI."""
    finished = pyqtSignal(dict, str)  # stats, formatted string
    auth_error = pyqtSignal(str)      # error message
    error = pyqtSignal(str)           # other error message

    def run(self):
        client = HubcapClient()
        if not client.has_api_key():
            self.auth_error.emit("No API key configured.")
            return

        try:
            stats = client.fetch_user_stats()
            formatted = extract_downloads_left(stats)
            self.finished.emit(stats, formatted)
        except HubcapAuthError as e:
            self.auth_error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))


class ManifestDownloadWorker(QThread):
    """Worker thread to download manifests and depot keys without blocking GUI."""
    finished = pyqtSignal(str, int)  # target_dir, file_count
    auth_error = pyqtSignal(str)     # error message
    not_found = pyqtSignal(str)      # 404 not found message
    error = pyqtSignal(str)          # other error message

    def __init__(self, app_id: int, game_name: str):
        super().__init__()
        self.app_id = app_id
        self.game_name = game_name

    def run(self):
        client = HubcapClient()
        try:
            target_dir, file_count = client.download_and_save(self.app_id, self.game_name)
            self.finished.emit(target_dir, file_count)
        except HubcapNotFoundError as e:
            self.not_found.emit(str(e))
        except HubcapAuthError as e:
            self.auth_error.emit(str(e))
        except Exception as e:
            if "404" in str(e):
                self.not_found.emit(str(e))
            else:
                self.error.emit(str(e))
