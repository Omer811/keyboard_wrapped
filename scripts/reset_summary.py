#!/usr/bin/env python3
"""Reset the daily keyboard summary and widget progress state."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.configuration import resolve_root, widget_paths

BASE_FIELDS = {
    "total_events": 0,
    "letters": 0,
    "actions": 0,
    "words": 0,
    "rage_clicks": 0,
    "long_pauses": 0,
    "daily_activity": {},
    "daily_rage": {},
    "daily_word_counts": {},
    "key_counts": {},
    "word_pairs": {},
    "word_shapes": {},
    "key_press_lengths": {},
    "word_durations": {},
    "device_meta": {},
    "word_counts": {},
    "word_pairs": {},
    "first_event": None,
    "last_event": None,
    "typing_profile": {
        "avg_interval": 0,
        "avg_press_length": 0,
        "wpm": 0,
        "avg_word_shape_samples": 0,
        "long_pause_rate": 0,
    },
    "word_accuracy": {"score": 0, "correct": 0, "incorrect": 0},
    "interval_stats": {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None},
    "speed_points": {
        "earned": 0,
        "sessions": 0,
        "last_avg_interval": 0,
        "last_accuracy_pct": 0,
        "target_sessions": 0,
    },
}

DEFAULT_PROGRESS_SNAPSHOT = {
    "timestamp": 0,
    "mode": "real",
    "keyProgress": 0,
    "keyTarget": 5000,
    "speedProgress": 0,
    "speedTarget": 120,
    "handshakeProgress": 0,
    "handshakeTarget": 80,
    "wordAccuracyScore": 0,
    "wordAccuracyTarget": 120,
}


def atomic_write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    temporary.replace(path)


def load_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_summary(path: Path, payload: dict):
    atomic_write(path, payload)


def reset_daily(path: Path):
    summary = load_summary(path)
    device_meta = summary.get("device_meta", {})
    new_summary = {**BASE_FIELDS}
    new_summary["device_meta"] = device_meta
    write_summary(path, new_summary)


def reset_widget_progress(path: Path, mode: str = "real"):
    snapshot = {**DEFAULT_PROGRESS_SNAPSHOT}
    snapshot["mode"] = mode
    snapshot["timestamp"] = time.time()
    atomic_write(path, snapshot)


def resolve_progress_path(root: Path, explicit: Optional[Path]):
    if explicit:
        return explicit if explicit.is_absolute() else root / explicit
    return widget_paths(root)["progress"]


def main():
    parser = argparse.ArgumentParser(description="Reset per-day keyboard stats for demos.")
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/summary.json"),
        help="Summary file to update.",
    )
    parser.add_argument("--progress", type=Path, help="Widget progress file to reset.")
    parser.add_argument("--health", type=Path, help="Optional health file to clear.")
    parser.add_argument(
        "--mode",
        choices=["real", "sample"],
        default="real",
        help="Label the widget mode for the progress snapshot.",
    )
    parser.add_argument("--root", type=Path, help="Project root (falls back to KEYBOARD_WRAPPED_ROOT).")
    args = parser.parse_args()

    root = resolve_root(args.root)
    summary_path = args.summary if args.summary.is_absolute() else root / args.summary
    progress_path = resolve_progress_path(root, args.progress)

    reset_daily(summary_path)
    reset_widget_progress(progress_path, mode=args.mode)
    if args.health:
        atomic_write(args.health, {"status": "stopped", "message": "Logger reset", "timestamp": time.time()})
    print(f"Daily stats reset for {summary_path}")


if __name__ == "__main__":
    main()
