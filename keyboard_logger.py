#!/usr/bin/env python3
"""Lightweight key press recorder tailored for a yearly “Wrapped” view."""

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from pynput import keyboard
except ImportError:  # pragma: no cover
    print(
        "pynput is required to run the logger. Install it with "
        "`pip install pynput` and rerun."
    )
    sys.exit(1)


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WrappedLogger:
    def __init__(self, log_path: Path, summary_path: Path, min_rage_interval_ms=450):
        self.log_path = log_path
        self.summary_path = summary_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_path, "a", encoding="utf-8")

        self.last_press_time = None
        self.last_key = None
        self.last_logged_key = None
        self.rage_streak = 0
        self.word_buffer = []
        self.previous_word = None
        self.current_day_label = None
        self.word_start = None
        self.word_last = None
        self.pending_keys = {}
        self.current_word_letter_events = []
        self.summary = self._load_existing_summary()
        self._ensure_schema()
        self.min_rage_interval_ms = min_rage_interval_ms

    def _load_existing_summary(self):
        if not self.summary_path.exists():
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
                "device_meta": self._capture_device_meta(),
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
        with open(self.summary_path, "r", encoding="utf-8") as existing:
            try:
                return json.load(existing)
            except json.JSONDecodeError:  # pragma: no cover
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
                    "device_meta": self._capture_device_meta(),
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

    def _ensure_schema(self):
        defaults = {
            "daily_rage": {},
            "daily_word_counts": {},
            "key_pairs": {},
            "key_press_lengths": {},
            "interval_stats": {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None},
            "word_durations": {},
            "word_shapes": {},
            "typing_profile": {
                "avg_interval": 0,
                "avg_press_length": 0,
                "wpm": 0,
                "avg_word_shape_samples": 0,
                "long_pause_rate": 0,
            },
        }
        for key, value in defaults.items():
            self.summary.setdefault(key, value)
        self.summary["device_meta"] = self._capture_device_meta()

    def _capture_device_meta(self):
        return {
            "platform": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

    def _write_event(self, event):
        self.log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.log_file.flush()

    def _record_interval(self, interval_ms):
        if interval_ms <= 0:
            return
        stats = self.summary.setdefault(
            "interval_stats", {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None}
        )
        stats["count"] += 1
        stats["total_ms"] += interval_ms
        stats["max_ms"] = max(stats["max_ms"], interval_ms)
        if stats["min_ms"] is None or interval_ms < stats["min_ms"]:
            stats["min_ms"] = interval_ms

    def _record_duration(self, key, duration_ms):
        if duration_ms is None:
            return
        lengths = self.summary.setdefault(
            "key_press_lengths",
            {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None},
        )
        key_stats = lengths.setdefault(key, {"count": 0, "total_ms": 0, "max_ms": 0, "min_ms": None})
        key_stats["count"] += 1
        key_stats["total_ms"] += duration_ms
        key_stats["max_ms"] = max(key_stats["max_ms"], duration_ms)
        if key_stats["min_ms"] is None or duration_ms < key_stats["min_ms"]:
            key_stats["min_ms"] = duration_ms

    def _record_word_shape(self, word):
        if not self.current_word_letter_events:
            return
        shapes = self.summary.setdefault("word_shapes", {}).setdefault(word, [])
        shapes.append(
            {
                "durations": [entry["duration_ms"] for entry in self.current_word_letter_events],
                "intervals": [entry["interval_ms"] for entry in self.current_word_letter_events],
            }
        )

    def _refresh_typing_profile(self):
        interval_stats = self.summary.get("interval_stats", {})
        count = interval_stats.get("count", 0)
        avg_interval = interval_stats.get("total_ms", 0) / count if count else 0
        key_lengths = self.summary.get("key_press_lengths", {})
        total_press_ms = sum(entry.get("total_ms", 0) for entry in key_lengths.values())
        total_press_count = sum(entry.get("count", 0) for entry in key_lengths.values())
        avg_press_length = total_press_ms / total_press_count if total_press_count else 0
        wpm = 60000 / avg_interval if avg_interval else 0
        word_shapes = self.summary.get("word_shapes", {})
        shapes_count = sum(len(values) for values in word_shapes.values())
        long_pause_rate = (
            self.summary.get("long_pauses", 0) / self.summary.get("total_events", 1)
        )
        profile = {
            "avg_interval": round(avg_interval, 1),
            "avg_press_length": round(avg_press_length, 1),
            "wpm": round(wpm, 1),
            "avg_word_shape_samples": shapes_count,
            "long_pause_rate": round(long_pause_rate, 3),
        }
        self.summary["typing_profile"] = profile

    def _record_transition(self, key):
        if self.last_logged_key:
            pairs = self.summary.setdefault("key_pairs", {}).setdefault(self.last_logged_key, {})
            pairs.setdefault(key, 0)
            pairs[key] += 1
        self.last_logged_key = key

    def _update_summary(self, event):
        self.summary["total_events"] += 1
        self.summary["key_counts"].setdefault(event["key"], 0)
        self.summary["key_counts"][event["key"]] += 1

        self._record_transition(event["key"])
        self._record_interval(event.get("interval_ms", 0))
        self._record_duration(event["key"], event.get("duration_ms"))

        if event["category"] == "letter":
            self.summary["letters"] += 1
        else:
            self.summary["actions"] += 1

        date_label = event["timestamp"][:10]
        if event["behaviors"].get("rage_click"):
            self.summary["rage_clicks"] += 1
            self.summary["daily_rage"].setdefault(date_label, 0)
            self.summary["daily_rage"][date_label] += 1

        if event["behaviors"].get("long_pause"):
            self.summary["long_pauses"] += 1

        self.summary["daily_activity"].setdefault(date_label, 0)
        self.summary["daily_activity"][date_label] += 1
        self.current_day_label = date_label

        self.summary["last_event"] = event["timestamp"]
        if self.summary["first_event"] is None:
            self.summary["first_event"] = event["timestamp"]

    def _finish_word(self, day_label=None, reset_sequence=False):
        label = day_label or self.current_day_label
        if label is None and self.summary.get("last_event"):
            label = self.summary["last_event"][:10]
        if self.word_buffer:
            word = "".join(self.word_buffer)
            if word:
                self.summary["words"] += 1
                self.summary["word_counts"].setdefault(word, 0)
                self.summary["word_counts"][word] += 1

                if self.previous_word:
                    pairs = self.summary["word_pairs"].setdefault(self.previous_word, {})
                    pairs.setdefault(word, 0)
                    pairs[word] += 1

                self.previous_word = word
                if label:
                    day_words = self.summary["daily_word_counts"].setdefault(label, {})
                    day_words.setdefault(word, 0)
                    day_words[word] += 1

                if self.word_start and self.word_last:
                    duration = int(
                        (self.word_last - self.word_start).total_seconds() * 1000
                    )
                    word_times = self.summary.setdefault("word_durations", {})
                    stats = word_times.setdefault(word, {"count": 0, "total_ms": 0, "fastest_ms": None, "slowest_ms": 0})
                    stats["count"] += 1
                    stats["total_ms"] += duration
                    stats["slowest_ms"] = max(stats["slowest_ms"], duration)
                    if stats["fastest_ms"] is None or duration < stats["fastest_ms"]:
                        stats["fastest_ms"] = duration
                self._record_word_shape(word)

            self.word_buffer = []
            self.word_start = None
            self.word_last = None
            self.current_word_letter_events = []

        if reset_sequence:
            self.previous_word = None
            self.current_word_letter_events = []

    def _normalize_key(self, key):
        if isinstance(key, keyboard.KeyCode) and key.char:
            return key.char
        return str(key).strip("Key.").lower()

    def _categorize(self, key):
        if isinstance(key, keyboard.KeyCode) and key.char:
            if key.char.isalpha():
                return "letter", True
            return "letter", False
        return "action", False

    def on_press(self, key):
        now = datetime.now(timezone.utc)
        ts = now.isoformat()
        date_label = ts[:10]
        interval_ms = (
            int((now - self.last_press_time).total_seconds() * 1000)
            if self.last_press_time
            else 0
        )

        normalized = self._normalize_key(key)
        category, is_letter = self._categorize(key)

        behaviors = {}
        if self.last_key == normalized and interval_ms and interval_ms < self.min_rage_interval_ms:
            self.rage_streak += 1
        else:
            self.rage_streak = 1

        if self.rage_streak >= 4:
            behaviors["rage_click"] = True

        if interval_ms > 2000:
            behaviors["long_pause"] = True
            self._finish_word(day_label=date_label, reset_sequence=True)

        if is_letter:
            self.word_buffer.append(normalized.lower())
            if self.word_start is None:
                self.word_start = now
            self.word_last = now
        else:
            if normalized in {"space", "enter", "tab"}:
                self._finish_word(day_label=date_label)

        event = {
            "timestamp": ts,
            "key": normalized,
            "category": category,
            "interval_ms": interval_ms,
            "behaviors": behaviors,
            "duration_ms": None,
        }

        self.pending_keys[key] = {"event": event, "press_time": now}
        self.last_press_time = now
        self.last_key = normalized

    def on_release(self, key):
        record = self.pending_keys.pop(key, None)
        if not record:
            return
        now = datetime.now(timezone.utc)
        duration_ms = int((now - record["press_time"]).total_seconds() * 1000)
        record["event"]["duration_ms"] = duration_ms
        if record["event"]["category"] == "letter":
            self.current_word_letter_events.append(
                {
                    "key": record["event"]["key"],
                    "duration_ms": duration_ms,
                    "interval_ms": record["event"].get("interval_ms", 0),
                }
            )
        self._write_event(record["event"])
        self._update_summary(record["event"])

    def _flush_pending_keys(self):
        for key in list(self.pending_keys.keys()):
            self.on_release(key)

    def stop(self):
        self._flush_pending_keys()
        self._finish_word(day_label=self.current_day_label)
        self._refresh_typing_profile()
        self.log_file.close()
        with open(self.summary_path, "w", encoding="utf-8") as summary_file:
            json.dump(self.summary, summary_file, ensure_ascii=False, indent=2)


def parse_args():
    parser = argparse.ArgumentParser(description="Capture a year's worth of key usage.")
    parser.add_argument(
        "--log",
        "-l",
        type=Path,
        default=Path("data/keystrokes.jsonl"),
        help="Where to append the raw keystroke events.",
    )
    parser.add_argument(
        "--summary",
        "-s",
        type=Path,
        default=Path("data/summary.json"),
        help="Where to write the rolling summary used by the UI.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = WrappedLogger(args.log, args.summary)
    print("Logger is running. Press Ctrl+C to stop and flush the summary.")

    with keyboard.Listener(on_press=logger.on_press, on_release=logger.on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            pass
        finally:
            logger.stop()


if __name__ == "__main__":
    main()
