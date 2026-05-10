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
