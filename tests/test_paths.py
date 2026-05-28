import os
import sys
from pathlib import Path
import pytest


def test_resource_path_in_source_mode_returns_project_relative_path(monkeypatch):
    """In source mode (no _MEIPASS), resource_path() resolves relative to paths.py's directory."""
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    from paths import resource_path
    result = resource_path("foo/bar.txt")
    assert result.name == "bar.txt"
    assert result.parent.name == "foo"


def test_resource_path_uses_meipass_when_frozen(monkeypatch, tmp_path):
    """When sys._MEIPASS is set (PyInstaller frozen mode), resource_path() resolves against it."""
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    from paths import resource_path
    result = resource_path("assets/cat.png")
    assert result == tmp_path / "assets" / "cat.png"


def test_user_data_dir_in_source_mode_returns_project_root(monkeypatch):
    """In source mode (sys.frozen unset), user_data_dir() returns the project directory."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    import paths
    from paths import user_data_dir
    result = user_data_dir()
    assert result == Path(paths.__file__).parent


def test_user_data_dir_when_frozen_uses_appdata_and_creates_dir(monkeypatch, tmp_path):
    """When frozen, user_data_dir() returns %APPDATA%\\PurrPause and ensures it exists."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "PurrPause"
    assert result.is_dir()
