"""
Build script to compile the Steam Game Search desktop app into a standalone Windows .exe.
"""

import subprocess
import sys
import os

def build():
    print("Building SteamDepotDownloaderModBuddy (SDDMB) executable with PyInstaller...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=SDDMB",
        "--windowed",
        "--onefile",
        "--clean",
        "app.py",
    ]
    result = subprocess.run(cmd, check=True)
    if result.returncode == 0:
        exe_path = os.path.abspath(os.path.join("dist", "SDDMB.exe"))
        print("\n=======================================================")
        print(f"SUCCESS! Standalone Windows executable created at:")
        print(exe_path)
        print("=======================================================")

if __name__ == "__main__":
    build()
