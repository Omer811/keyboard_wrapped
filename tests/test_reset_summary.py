from pathlib import Path

import json

from keyboard_logger import WrappedLogger
from scripts.reset_summary import reset_daily, reset_widget_progress


def test_reset_summary(tmp_path: Path):
    summary = {
        "total_events": 1200,
        "daily_activity": {"2025-01-01": 250},
        "daily_word_counts": {"2025-01-01": {"hello": 3}},
        "daily_rage": {"2025-01-01": 2},
        "rage_clicks": 5,
        "long_pauses": 4,
        "key_counts": {"a": 10},
        "word_accuracy": {"score": 12, "correct": 5, "incorrect": 2},
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary))

    reset_daily(path)
    updated = json.loads(path.read_text())
    assert updated["daily_activity"] == {}
    assert updated["daily_word_counts"] == {}
    assert updated["daily_rage"] == {}
    assert updated["rage_clicks"] == 0
    assert updated["long_pauses"] == 0
    assert updated["key_counts"] == {}
    assert updated["word_accuracy"]["score"] == 0
    assert updated["first_event"] is None
    assert updated["last_event"] is None


def test_reset_widget_progress(tmp_path: Path):
    path = tmp_path / "widget_progress.json"
    path.write_text(
        json.dumps(
            {
                "keyProgress": 4000,
                "speedProgress": 80,
                "handshakeProgress": 10,
                "mode": "real",
                "wordAccuracyScore": 12,
            }
        )
    )

    reset_widget_progress(path, mode="sample")
    payload = json.loads(path.read_text())
    assert payload["keyProgress"] == 0
    assert payload["speedProgress"] == 0
    assert payload["handshakeProgress"] == 0
    assert payload["wordAccuracyScore"] == 0
    assert payload["mode"] == "sample"
    assert payload["timestamp"] > 0


def test_logger_can_write_after_reset(tmp_path: Path):
    summary = tmp_path / "data" / "summary.json"
    log_path = tmp_path / "data" / "keystrokes.jsonl"
    reset_daily(summary)
    logger = WrappedLogger(log_path, summary, log_mode=True)
    event = {
        "timestamp": "2025-01-01T00:00:00+00:00",
        "key": "a",
        "category": "letter",
        "interval_ms": 25,
        "behaviors": {},
        "duration_ms": 30,
    }
    logger._write_event(event)
    logger._update_summary(event)
    logger.log_file.close()
    data = json.loads(summary.read_text())
    assert data["total_events"] == 1
    assert data["first_event"] == "2025-01-01T00:00:00+00:00"
    assert data["last_event"] == "2025-01-01T00:00:00+00:00"
