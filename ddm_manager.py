"""
DepotDownloaderMod (DDM) execution manager, Lua manifest parsing, and credential storage.
Handles:
- Locating DDM executable and depotkeys.txt
- Parsing .lua manifest files to extract AppID, DepotID, and decryption keys
- Updating DDM/depotkeys.txt automatically
- Managing Steam username and credentials persistence in QSettings
- Building DDM command line arguments
"""

import sys
import os
import re
import shutil
from typing import Optional, List, Dict, Tuple, Any
from PyQt6.QtCore import QSettings


def get_base_dir() -> str:
    """
    Get the application root directory containing DDM, UC2, Steamless.
    Handles both normal script execution and PyInstaller frozen .exe execution.
    """
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(exe_dir)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(meipass)
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.getcwd())

    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "DDM")):
            return c
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return os.getcwd()


BASE_DIR = get_base_dir()
DDM_DIR = os.path.join(BASE_DIR, "DDM")
DDM_EXE = os.path.join(DDM_DIR, "DepotDownloaderMod.exe")
DEPOTKEYS_TXT = os.path.join(DDM_DIR, "depotkeys.txt")
UC2_DIR = os.path.join(BASE_DIR, "UC2")
UC2_STEAMAPI_DLL = os.path.join(UC2_DIR, "steam_api64.dll")

SETTINGS_ORG = "SteamSearch"
SETTINGS_APP = "SteamGameSearch"
KEY_STEAM_USER = "steam_username"
KEY_STEAM_SAVED = "steam_creds_saved"
KEY_LAST_DOWNLOAD_DIR = "last_download_base_dir"


def sanitize_folder_name(name: str) -> str:
    """Sanitize game title for safe Windows folder naming."""
    # Remove characters illegal in Windows file paths: \ / : * ? " < > |
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return sanitized if sanitized else "Game"


def get_steam_credentials() -> Tuple[str, bool]:
    """Retrieve stored Steam username and remember-password flag."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    username = str(settings.value(KEY_STEAM_USER, "") or "").strip()
    saved = bool(settings.value(KEY_STEAM_SAVED, False))
    return username, saved


def save_steam_credentials(username: str, creds_saved: bool = True):
    """Store Steam username and remember-password flag."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(KEY_STEAM_USER, username.strip())
    settings.setValue(KEY_STEAM_SAVED, creds_saved)


def clear_steam_credentials():
    """Clear stored Steam credentials."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.remove(KEY_STEAM_USER)
    settings.remove(KEY_STEAM_SAVED)


def get_last_download_dir() -> str:
    """Retrieve last chosen base download directory, default to user's Downloads or Games folder."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    val = settings.value(KEY_LAST_DOWNLOAD_DIR, "")
    if val and os.path.isdir(str(val)):
        return str(val)
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(downloads):
        return downloads
    return os.path.expanduser("~")


def save_last_download_dir(directory: str):
    """Save the last chosen download directory."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(KEY_LAST_DOWNLOAD_DIR, directory)


def parse_lua_file(lua_path: str, app_id: int) -> Dict[str, Any]:
    """
    Parse a Steam/Hubcap .lua script.
    Extracts:
    - primary_depot: the first depot ID found in addappid(depot_id, ...)
    - all_depots: list of all depot IDs
    - keys: mapping of depot_id -> 64-char hex key
    - manifests: mapping of depot_id -> manifest_id string
    """
    if not os.path.isfile(lua_path):
        return {"primary_depot": None, "all_depots": [], "keys": {}, "manifests": {}}

    try:
        with open(lua_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return {"primary_depot": None, "all_depots": [], "keys": {}, "manifests": {}}

    # Matches: addappid(ID, FLAG [, "KEY"])
    add_pattern = re.compile(
        r'addappid\s*\(\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*["\']([a-fA-F0-9]{32,64})["\'])?',
        re.IGNORECASE
    )

    depots: List[int] = []
    keys: Dict[int, str] = {}

    for match in add_pattern.finditer(content):
        matched_id = int(match.group(1))
        hex_key = match.group(3)
        if hex_key:
            keys[matched_id] = hex_key

        # If ID is not the main app ID, it's a depot!
        if matched_id != app_id:
            if matched_id not in depots:
                depots.append(matched_id)

    # Matches: setManifestid(DEPOT_ID, "MANIFEST_ID", SIZE)
    manifest_pattern = re.compile(
        r'setManifestid\s*\(\s*(\d+)\s*,\s*["\']?(\d+)["\']?',
        re.IGNORECASE
    )
    manifests: Dict[int, str] = {}
    for match in manifest_pattern.finditer(content):
        depot_id = int(match.group(1))
        manifest_id = match.group(2)
        manifests[depot_id] = manifest_id

    # If all_depots is empty, check if any addappid exists
    if not depots:
        all_ids = [int(m.group(1)) for m in add_pattern.finditer(content)]
        if all_ids:
            depots = all_ids

    primary_depot = depots[0] if depots else None

    # Sync keys to depotkeys.txt
    if keys:
        update_depotkeys_file(keys)

    return {
        "primary_depot": primary_depot,
        "all_depots": depots,
        "keys": keys,
        "manifests": manifests,
    }


def update_depotkeys_file(keys: Dict[int, str]):
    """
    Append or update depot keys in DDM/depotkeys.txt.
    Format: depotID;hexKey
    """
    if not os.path.isdir(DDM_DIR):
        return

    existing_lines = []
    existing_depots = set()
    if os.path.isfile(DEPOTKEYS_TXT):
        try:
            with open(DEPOTKEYS_TXT, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and ";" in stripped:
                        existing_lines.append(stripped)
                        depot_part = stripped.split(";")[0].strip()
                        if depot_part.isdigit():
                            existing_depots.add(int(depot_part))
        except Exception:
            pass

    new_entries = []
    for depot_id, key in keys.items():
        if depot_id not in existing_depots:
            new_entries.append(f"{depot_id};{key}")
            existing_depots.add(depot_id)

    if new_entries:
        try:
            with open(DEPOTKEYS_TXT, "a", encoding="utf-8") as f:
                for entry in new_entries:
                    f.write(f"\n{entry}")
        except Exception:
            pass


def find_manifest_file(games_dir: str, depot_id: Optional[int], manifest_id: Optional[str]) -> Optional[str]:
    """Find matching .manifest file in the downloaded game files directory."""
    if not os.path.isdir(games_dir):
        return None

    files = os.listdir(games_dir)
    manifest_files = [f for f in files if f.endswith(".manifest")]

    if not manifest_files:
        return None

    # 1. Look for exact match containing manifest_id
    if manifest_id:
        for mf in manifest_files:
            if manifest_id in mf:
                return os.path.join(games_dir, mf)

    # 2. Look for match containing depot_id
    if depot_id:
        for mf in manifest_files:
            if str(depot_id) in mf:
                return os.path.join(games_dir, mf)

    # 3. Fallback to first .manifest file
    return os.path.join(games_dir, manifest_files[0])


def generate_depotkeys_file_from_lua(lua_path: str, output_txt_path: str) -> Optional[str]:
    """
    Extract depot keys from a .lua file and write them to a text file in format:
    depotID;hexKey per line (first value of addappid and third value of addappid).
    Returns the path to the created file if keys were found/written, else None.
    """
    if not os.path.isfile(lua_path):
        return None

    try:
        with open(lua_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return None

    add_pattern = re.compile(
        r'addappid\s*\(\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*["\']([a-fA-F0-9]{32,64})["\'])?',
        re.IGNORECASE
    )

    lines = []
    seen_depots = set()
    for match in add_pattern.finditer(content):
        depot_id = match.group(1)
        hex_key = match.group(3)
        if hex_key and depot_id not in seen_depots:
            seen_depots.add(depot_id)
            lines.append(f"{depot_id};{hex_key}")

    if not lines:
        return None

    os.makedirs(os.path.dirname(os.path.abspath(output_txt_path)), exist_ok=True)
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return output_txt_path


def build_ddm_command(
    app_id: int,
    depot_id: int,
    install_dir: str,
    username: str,
    password: Optional[str] = None,
    remember_password: bool = True,
    manifest_id: Optional[str] = None,
    manifest_file: Optional[str] = None,
    depotkeys_file: Optional[str] = None,
) -> List[str]:
    """
    Construct the argument list for DepotDownloaderMod.exe.
    Format:
    DepotDownloaderMod.exe -app <AppID> -depot <DepotID> -dir "<install_dir>"
    [-depotkeys <file>]
    [-username <user> [-password <pass>]] [-remember-password]
    [-manifest <id> | -manifestfile <path>]
    """
    args = [
        DDM_EXE,
        "-app", str(app_id),
        "-depot", str(depot_id),
        "-dir", install_dir,
    ]

    if depotkeys_file:
        args.extend(["-depotkeys", depotkeys_file])

    if username:
        args.extend(["-username", username])

    if password:
        args.extend(["-password", password])

    if remember_password:
        args.append("-remember-password")

    if manifest_file and os.path.isfile(manifest_file):
        args.extend(["-manifestfile", manifest_file])
    elif manifest_id:
        args.extend(["-manifest", str(manifest_id)])

    return args


def replace_steam_api_dll(install_dir: str, uc2_dir: Optional[str] = None) -> List[Tuple[str, str]]:
    """
    Recursively searches install_dir for steam_api64.dll.
    Renames the original file to .original (steam_api64.dll.original)
    and replaces it with UC2\\steam_api64.dll.
    Also copies union-crax.ini if present in uc2_dir.
    Returns a list of tuples: (replaced_file_path, original_backup_path)
    """
    if not install_dir or not os.path.isdir(install_dir):
        return []

    if uc2_dir is None:
        uc2_dir = UC2_DIR

    source_dll = os.path.join(uc2_dir, "steam_api64.dll")
    if not os.path.isfile(source_dll):
        return []

    replaced: List[Tuple[str, str]] = []

    for root, dirs, files in os.walk(install_dir):
        for file in files:
            if file.lower() == "steam_api64.dll":
                target_path = os.path.join(root, file)
                original_backup = target_path + ".original"

                if os.path.exists(original_backup):
                    try:
                        os.remove(original_backup)
                    except Exception:
                        pass

                # 1. Rename original to .original
                os.rename(target_path, original_backup)

                # 2. Copy UC2 steam_api64.dll to target
                shutil.copy2(source_dll, target_path)

                # 3. Also copy union-crax.ini if available
                ini_source = os.path.join(uc2_dir, "union-crax.ini")
                if os.path.isfile(ini_source):
                    ini_target = os.path.join(root, "union-crax.ini")
                    try:
                        shutil.copy2(ini_source, ini_target)
                    except Exception:
                        pass

                replaced.append((target_path, original_backup))

    return replaced


def place_union_crax_ini(install_dir: str, uc2_dir: Optional[str] = None) -> Optional[str]:
    r"""
    Recursively searches install_dir for the first .exe file
    and places UC2\union-crax.ini next to it.
    Returns the path to the placed union-crax.ini if successful, else None.
    """
    if not install_dir or not os.path.isdir(install_dir):
        return None

    if uc2_dir is None:
        uc2_dir = UC2_DIR

    source_ini = os.path.join(uc2_dir, "union-crax.ini")
    if not os.path.isfile(source_ini):
        return None

    for root, dirs, files in os.walk(install_dir):
        for file in files:
            if file.lower().endswith(".exe"):
                dest_ini = os.path.join(root, "union-crax.ini")
                try:
                    shutil.copy2(source_ini, dest_ini)
                    return dest_ini
                except Exception:
                    pass
                return None

    return None
