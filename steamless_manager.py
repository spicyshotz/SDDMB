import os
import subprocess
import sys
from pathlib import Path
import re
import shutil
from typing import Optional, List, Dict, Tuple, Any, Callable
from PyQt6.QtCore import QSettings

def get_base_dir() -> str:
    """
    Get the application root directory containing Steamless.
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
        if c and os.path.isdir(os.path.join(c, "Steamless")):
            return c
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return os.getcwd()


STEAMLESS_DIR = os.path.join(get_base_dir(), "Steamless")
STEAMLESSCLI_EXE = os.path.join(STEAMLESS_DIR, "Steamless.CLI.exe")

def unpack_executable(target_exe: Path, log_fn: Optional[Callable[[str], None]] = None) -> bool:
    """Runs Steamless against a target executable and renames upon success."""
    log = log_fn if log_fn is not None else print
    
    cmd = [str(STEAMLESSCLI_EXE), "--quiet", str(target_exe)]

    # Suppress console window creation on Windows
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            creationflags=creation_flags,
        )
    except FileNotFoundError:
        log(f"Error: Steamless executable not found at '{STEAMLESSCLI_EXE}'")

    # Steamless generates <filename>.unpacked.exe in the same folder
    unpacked_exe = target_exe.with_name(f"{target_exe.name}.unpacked.exe")

    # Exit code 0 indicates success, but verify file existence to ensure clean unpack
    if result.returncode == 0 and unpacked_exe.exists():
        backup_exe = target_exe.with_name(f"{target_exe.name}.ORIGINAL")

        # Swap names: original -> .ORIGINAL, unpacked -> original name
        target_exe.rename(backup_exe)
        unpacked_exe.rename(target_exe)

        log(f"[+] Successfully unpacked and swapped: {target_exe}")
        log(f"    Original backed up to: {backup_exe.name}")
        return True

    return False