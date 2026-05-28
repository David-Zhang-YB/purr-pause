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
    """Return the writable user-data directory.

    Frozen mode: %APPDATA%\\PurrPause (created if missing).
    Source mode: the project root (so dev experience matches existing behavior).
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        d = root / "PurrPause"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).parent
