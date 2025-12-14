import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_WIDGET_CONFIG = {
    "progress_path": "data/widget_progress.json",
    "gpt_feed_path": "data/widget_gpt_feed.json",
    "gpt_state_path": "data/widget_gpt_state.json",
    "health_path": "data/widget_health.json",
    "debug_log_path": "data/widget_debug.log",
}


def resolve_root(root: Optional[Path] = None) -> Path:
    if root:
        return root
    env_root = os.environ.get("KEYBOARD_WRAPPED_ROOT")
    if env_root:
        return Path(env_root)
    return Path.cwd()


def config_path(root: Optional[Path] = None) -> Path:
    return resolve_root(root) / "config" / "app.json"


def load_app_config(root: Optional[Path] = None) -> Dict[str, Any]:
    path = config_path(root)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def widget_paths(
    root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Path]:
    resolved_root = resolve_root(root)
    raw = config or load_app_config(resolved_root)
    widget = raw.get("widget", {})
    return {
        "health": resolved_root / widget.get("health_path", DEFAULT_WIDGET_CONFIG["health_path"]),
        "debug": resolved_root / widget.get("debug_log_path", DEFAULT_WIDGET_CONFIG["debug_log_path"]),
        "progress": resolved_root / widget.get(
            "progress_path", DEFAULT_WIDGET_CONFIG["progress_path"]
        ),
        "gpt_feed": resolved_root / widget.get(
            "gpt_feed_path", DEFAULT_WIDGET_CONFIG["gpt_feed_path"]
        ),
        "gpt_state": resolved_root / widget.get(
            "gpt_state_path", DEFAULT_WIDGET_CONFIG["gpt_state_path"]
        ),
    }


def load_widget_settings(
    root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    raw = config or load_app_config(root)
    widget = raw.get("widget", {})
    accuracy = raw.get("word_accuracy", {})
    return {
        "sample_total_ratio": float(widget.get("sample_total_ratio", 0.05)),
        "sample_avg_interval": float(widget.get("sample_avg_interval", 210)),
        "sample_window_days": int(widget.get("sample_window_days", 14)),
        "progress_path": widget.get("progress_path", DEFAULT_WIDGET_CONFIG["progress_path"]),
        "accuracy_target": float(accuracy.get("target_score", 120)),
    }
