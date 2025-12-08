#!/usr/bin/env python3
"""Lightweight key press recorder tailored for a yearly “Wrapped” view."""

import argparse
import json
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
        self.rage_streak = 0
        self.word_buffer = []
        self.previous_word = None
        self.current_day_label = None
        self.summary = self._load_existing_summary()
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
                "word_counts": {},
                "word_pairs": {},
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
                    "word_counts": {},
                    "word_pairs": {},
                }

    def _write_event(self, event):
        self.log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.log_file.flush()

    def _update_summary(self, event):
        self.summary["total_events"] += 1
        self.summary["key_counts"].setdefault(event["key"], 0)
        self.summary["key_counts"][event["key"]] += 1

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

            self.word_buffer = []

        if reset_sequence:
            self.previous_word = None

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
        else:
            if normalized in {"space", "enter", "tab"}:
                self._finish_word(day_label=date_label)

        event = {
            "timestamp": ts,
            "key": normalized,
            "category": category,
            "interval_ms": interval_ms,
            "behaviors": behaviors,
        }

        self._write_event(event)
        self._update_summary(event)
        self.last_press_time = now
        self.last_key = normalized

    def stop(self):
        self._finish_word(day_label=self.current_day_label)
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

    with keyboard.Listener(on_press=logger.on_press) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            pass
        finally:
            logger.stop()


if __name__ == "__main__":
    main()
