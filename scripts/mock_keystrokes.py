#!/usr/bin/env python3
"""Simulate keystrokes to validate logger+widget plumbing without a physical keyboard."""

import argparse
import json
import math
import time
from pathlib import Path
from string import ascii_letters
from typing import Any, Dict, Iterable, List, Optional

from scripts.logger_health import append_debug
from scripts.configuration import load_app_config as load_config
from scripts.word_checker import WordChecker

LONG_PAUSE_THRESHOLD_MS = 800


def _default_summary() -> Dict[str, Any]:
    return {
        "total_events": 0,
        "letters": 0,
        "actions": 0,
        "words": 0,
        "rage_clicks": 0,
        "long_pauses": 0,
        "first_event": None,
        "last_event": None,
        "key_counts": {},
        "daily_activity": {},
        "daily_rage": {},
        "daily_word_counts": {},
        "key_pairs": {},
        "key_press_lengths": {},
        "interval_stats": {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None},
        "word_durations": {},
        "device_meta": {},
        "word_counts": {},
        "word_pairs": {},
        "word_shapes": {},
        "typing_profile": {
            "avg_interval": 0,
            "avg_press_length": 0,
            "wpm": 0,
            "avg_word_shape_samples": 0,
            "long_pause_rate": 0,
        },
    }


def load_summary(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return _default_summary()
    with path.open("r", encoding="utf-8") as fh:
        existing = json.load(fh)
    summary = {**_default_summary(), **existing}
    # ensure nested defaults exist
    summary.setdefault("typing_profile", _default_summary()["typing_profile"])
    summary.setdefault("interval_stats", _default_summary()["interval_stats"])
    summary.setdefault("key_pairs", {})
    summary.setdefault("key_press_lengths", {})
    return summary


def persist_summary(summary: Dict[str, Any], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)


def append_keystroke(event: Dict[str, Any], log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def record_event(
    summary: Dict[str, Any],
    key: str,
    interval_ms: float,
    duration_ms: float,
    timestamp: Optional[float] = None,
    previous_key: Optional[str] = None,
) -> Dict[str, Any]:
    if timestamp is None:
        timestamp = time.time()
    total = summary.get("total_events", 0) + 1
    summary["total_events"] = total
    if key and key[0].lower() in ascii_letters:
        summary["letters"] = summary.get("letters", 0) + 1
    else:
        summary["actions"] = summary.get("actions", 0) + 1
    if interval_ms >= LONG_PAUSE_THRESHOLD_MS:
        summary["long_pauses"] = summary.get("long_pauses", 0) + 1
    summary["last_event"] = timestamp
    summary["first_event"] = summary.get("first_event") or timestamp
    summary["key_counts"][key] = summary["key_counts"].get(key, 0) + 1

    key_pairs = summary.setdefault("key_pairs", {})
    if previous_key:
        target = key_pairs.setdefault(previous_key, {})
        target[key] = target.get(key, 0) + 1

    lengths = summary.setdefault("key_press_lengths", {})
    key_stats = lengths.setdefault(
        key, {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None}
    )
    key_stats["count"] += 1
    key_stats["total_ms"] += duration_ms
    key_stats["max_ms"] = max(key_stats["max_ms"], duration_ms)
    if key_stats["min_ms"] is None or duration_ms < key_stats["min_ms"]:
        key_stats["min_ms"] = duration_ms

    interval_stats = summary.setdefault(
        "interval_stats", {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None}
    )
    interval_stats["count"] += 1
    interval_stats["total_ms"] += interval_ms
    interval_stats["max_ms"] = max(interval_stats["max_ms"], interval_ms)
    if interval_stats["min_ms"] is None or interval_ms < interval_stats["min_ms"]:
        interval_stats["min_ms"] = interval_ms

    typing = summary.setdefault("typing_profile", {})
    count = interval_stats["count"]
    avg_interval = interval_stats["total_ms"] / count if count else 0
    typing["avg_interval"] = round(avg_interval, 1)
    total_length = sum(stats["total_ms"] for stats in lengths.values())
    total_count = sum(stats["count"] for stats in lengths.values())
    typing["avg_press_length"] = round(total_length / total_count, 1) if total_count else 0
    typing["wpm"] = round(60000 / avg_interval, 1) if avg_interval else 0
    typing["long_pause_rate"] = round(
        summary.get("long_pauses", 0) / max(summary["total_events"], 1), 3
    )
    return {
        "timestamp": timestamp,
        "key": key,
        "interval_ms": interval_ms,
        "duration_ms": duration_ms,
    }


def inject_keys(
    keys: Iterable[str],
    summary_path: Path,
    keystroke_path: Path,
    debug_path: Optional[Path] = None,
    interval_ms: float = 120.0,
    duration_ms: float = 60.0,
):
    summary = load_summary(summary_path)
    previous = None
    events: List[Dict[str, Any]] = []
    for key in keys:
        event = record_event(summary, key, interval_ms, duration_ms, previous_key=previous)
        append_keystroke(event, keystroke_path)
        events.append(event)
        previous = key
    persist_summary(summary, summary_path)
    _score_mock_word(summary, keys)
    if debug_path:
        append_debug(
            f"Mock injected {len(events)} events ending on {events[-1]['key']}",
            debug_path,
        )
    return summary, events


def main():
    parser = argparse.ArgumentParser(description="Mock keystrokes for debugging widget plumbing.")
    parser.add_argument(
        "--sequence",
        "-s",
        type=str,
        default="abc",
        help="Key names to inject sequentially (default: abc).",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=120.0,
        help="Interval between presses in milliseconds.",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=60.0,
        help="Duration of each key press in milliseconds.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/summary.json"),
        help="Summary file to update.",
    )
    parser.add_argument(
        "--keystrokes",
        type=Path,
        default=Path("data/keystrokes.jsonl"),
        help="Keystroke log file to append.",
    )
    parser.add_argument(
        "--debug-log",
        type=Path,
        default=Path("data/widget_debug.log"),
        help="Optional debug log for traceable output.",
    )
    args = parser.parse_args()
    inject_keys(
        keys=list(args.sequence),
        summary_path=args.summary,
        keystroke_path=args.keystrokes,
        debug_path=args.debug_log,
        interval_ms=args.interval,
        duration_ms=args.duration,
    )


def _score_mock_word(summary: Dict[str, Any], keys: Iterable[str]):
    word = "".join(str(key).lower() for key in keys if str(key).isalpha())
    if not word:
        return
    config = load_config()
    accuracy_config = config.get("word_accuracy", {})
    points = {
        "correct": float(accuracy_config.get("correct_points", 1)),
        "incorrect": float(accuracy_config.get("incorrect_points", -2)),
    }
    checker_kwargs = {
        "threshold": float(accuracy_config.get("threshold", 2.5)),
        "min_length": int(accuracy_config.get("min_word_length", 1)),
        "extra_words": accuracy_config.get("extra_words") or [],
    }
    checker = WordChecker(**checker_kwargs)
    accuracy = summary.setdefault(
        "word_accuracy",
        {"score": 0, "correct": 0, "incorrect": 0},
    )
    is_correct = checker.is_correct(word)
    key = "correct" if is_correct else "incorrect"
    accuracy[key] += 1
    accuracy["score"] = accuracy.get("score", 0) + points[key]


if __name__ == "__main__":
    main()
