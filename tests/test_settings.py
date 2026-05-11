import json
import pytest
from pathlib import Path


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """将 settings 模块的路径常量重定向到临时目录。"""
    default = tmp_path / "config.default.json"
    default.write_text(
        json.dumps({"interval_minutes": 20, "cat_image_path": ""}),
        encoding="utf-8",
    )
    import settings
    monkeypatch.setattr(settings, "DEFAULT_CONFIG_PATH", default)
    monkeypatch.setattr(settings, "CONFIG_PATH", tmp_path / "config.json")
    return tmp_path


def test_load_config_copies_default_when_missing(cfg):
    from settings import load_config
    config = load_config()

    assert config["interval_minutes"] == 20
    assert (cfg / "config.json").exists()


def test_load_config_reads_existing_file(cfg):
    from settings import load_config, save_config
    save_config({"interval_minutes": 30, "cat_image_path": ""})
    config = load_config()

    assert config["interval_minutes"] == 30


def test_save_config_persists(cfg):
    from settings import load_config, save_config
    load_config()  # 先创建 config.json
    save_config({"interval_minutes": 15, "cat_image_path": ""})

    import settings
    raw = json.loads(settings.CONFIG_PATH.read_text(encoding="utf-8"))
    assert raw["interval_minutes"] == 15


def test_settings_dialog_shows_current_interval(qtbot):
    from settings import SettingsDialog
    dialog = SettingsDialog(current_interval=25)
    qtbot.addWidget(dialog)

    assert dialog.spinbox.value() == 25


def test_settings_dialog_emits_interval_changed_on_save(qtbot):
    from settings import SettingsDialog
    dialog = SettingsDialog(current_interval=20)
    qtbot.addWidget(dialog)
    dialog.spinbox.setValue(35)

    with qtbot.waitSignal(dialog.interval_changed, timeout=500) as blocker:
        dialog._save()

    assert blocker.args == [35]


def test_settings_dialog_cancel_does_not_emit(qtbot):
    from settings import SettingsDialog
    dialog = SettingsDialog(current_interval=20)
    qtbot.addWidget(dialog)

    with qtbot.assertNotEmitted(dialog.interval_changed, wait=100):
        dialog.reject()


def test_settings_dialog_emits_image_path_changed_on_save(qtbot):
    from settings import SettingsDialog
    dialog = SettingsDialog(current_interval=20, current_image_path="")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.image_path_changed, timeout=500) as blocker:
        dialog._save()

    assert isinstance(blocker.args[0], str)


def test_settings_dialog_shows_current_image_name(qtbot):
    from settings import SettingsDialog
    dialog = SettingsDialog(current_interval=20, current_image_path="C:/cats/nyan.gif")
    qtbot.addWidget(dialog)

    assert dialog._img_label.text() == "nyan.gif"


def test_settings_dialog_shows_current_rest_duration(qtbot):
    from settings import SettingsDialog
    dialog = SettingsDialog(current_interval=20, current_rest_duration=30)
    qtbot.addWidget(dialog)

    assert dialog.rest_spinbox.value() == 30


def test_settings_dialog_emits_rest_duration_changed_on_save(qtbot):
    from settings import SettingsDialog
    dialog = SettingsDialog(current_interval=20, current_rest_duration=20)
    qtbot.addWidget(dialog)
    dialog.rest_spinbox.setValue(35)

    with qtbot.waitSignal(dialog.rest_duration_changed, timeout=500) as blocker:
        dialog._save()

    assert blocker.args == [35]
