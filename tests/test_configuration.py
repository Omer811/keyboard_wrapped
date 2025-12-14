import json
from pathlib import Path

import pytest

from scripts.configuration import (
    DEFAULT_WIDGET_CONFIG,
    load_app_config,
    load_widget_settings,
    resolve_root,
    widget_paths,
)


def test_widget_paths_default(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("KEYBOARD_WRAPPED_ROOT", str(tmp_path))
    assert resolve_root() == tmp_path
    config = load_app_config()
    assert config == {}
    paths = widget_paths()
    assert paths["progress"].name == Path(DEFAULT_WIDGET_CONFIG["progress_path"]).name
    assert paths["health"].name == Path(DEFAULT_WIDGET_CONFIG["health_path"]).name


def test_widget_paths_respects_config(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    payload = {
        "widget": {
            "progress_path": "custom/progress.json",
            "health_path": "custom/health.json",
            "debug_log_path": "custom/debug.log",
        },
        "word_accuracy": {"target_score": 88},
    }
    config_file = config_dir / "app.json"
    config_file.write_text(json.dumps(payload))
    monkeypatch.setenv("KEYBOARD_WRAPPED_ROOT", str(tmp_path))
    config = load_app_config()
    paths = widget_paths(config=config, root=tmp_path)
    assert paths["progress"].name == "progress.json"
    assert paths["health"].name == "health.json"
    settings = load_widget_settings(config=config)
    assert settings["accuracy_target"] == 88.0
    assert settings["sample_total_ratio"] == 0.05
