import os
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Resolve a bundled read-only resource path.

    Works in source mode (returns project_root/rel) and in PyInstaller
    --onefile frozen mode (returns _MEIPASS_temp_dir/rel).
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / rel


def user_data_dir() -> Path:
    """Return the writable user-data directory, per-OS convention.

    Source mode: project root (matches existing dev behavior).
    Frozen mode:
      - Windows: %APPDATA%\\PurrPause (or ~/AppData/Roaming/PurrPause)
      - macOS:   ~/Library/Application Support/PurrPause
      - Linux:   $XDG_CONFIG_HOME/PurrPause (or ~/.config/PurrPause)
    """
    if not getattr(sys, "frozen", False):
        return Path(__file__).parent

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        root = Path(xdg) if xdg else Path.home() / ".config"

    d = root / "PurrPause"
    d.mkdir(parents=True, exist_ok=True)
    return d
