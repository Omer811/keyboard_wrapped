import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .configuration import widget_paths as configuration_widget_paths


def widget_paths(
    root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Path]:
    return configuration_widget_paths(root, config)


def write_health_status(
    status: str,
    message: Optional[str] = None,
    root: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
):
    paths = widget_paths(root, config)
    payload = {
        "status": status,
        "message": message or "",
        "timestamp": int(time.time()),
    }
    paths["health"].parent.mkdir(parents=True, exist_ok=True)
    with paths["health"].open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    append_debug(message or status, paths["debug"])


def append_debug(message: str, debug_path: Optional[Path] = None):
    if not message:
        return
    path = debug_path or widget_paths()["debug"]
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{timestamp} {message}\n")


def load_health_status(root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None):
    paths = widget_paths(root, config)
    if not paths["health"].exists():
        return {}
    with paths["health"].open("r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return {}
