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


def test_user_data_dir_frozen_windows_uses_appdata(monkeypatch, tmp_path):
    """On Windows frozen, %APPDATA%\\PurrPause is created and returned."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_windows_no_appdata_falls_back_to_home(monkeypatch, tmp_path):
    """Without APPDATA env, fall back to ~/AppData/Roaming/PurrPause."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "AppData" / "Roaming" / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_macos_uses_application_support(monkeypatch, tmp_path):
    """On macOS frozen, ~/Library/Application Support/PurrPause is created and returned."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "Library" / "Application Support" / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_linux_uses_xdg_config_home(monkeypatch, tmp_path):
    """On Linux frozen with XDG_CONFIG_HOME set, use $XDG_CONFIG_HOME/PurrPause."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "xdg" / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_linux_no_xdg_falls_back_to_home_config(monkeypatch, tmp_path):
    """Without XDG_CONFIG_HOME, fall back to ~/.config/PurrPause."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / ".config" / "PurrPause"
    assert result.is_dir()
