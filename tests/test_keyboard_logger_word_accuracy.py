
import json
import os
from pathlib import Path

import pytest
from pynput import keyboard

from keyboard_logger import WrappedLogger

def make_logger_with_speed_config(tmp_path: Path, speed_config: dict):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config = {"speed_points": speed_config}
    (config_dir / "app.json").write_text(json.dumps(config))
    os.environ["KEYBOARD_WRAPPED_ROOT"] = str(tmp_path)
    summary = tmp_path / "data" / "summary.json"
    log_path = tmp_path / "data" / "keystrokes.jsonl"
    return WrappedLogger(log_path, summary, log_mode=True)


class DummyLogger(WrappedLogger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scored = []

    def _score_word(self, word: str) -> bool:  # type: ignore[override]
        self.scored.append(word)
        return super()._score_word(word)


def simulate_word(logger: WrappedLogger, word: str):
    previous = None
    for char in word:
        key = keyboard.KeyCode.from_char(char)
        logger.on_press(key)
        logger.on_release(key)
        previous = key
    # press space to finish the word
    logger.on_press(keyboard.Key.space)


def test_score_word_updates_summary(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "keystrokes.jsonl"
    summary_path = tmp_path / "summary.json"
    messages = []

    def fake_debug(msg, _=None):
        messages.append(msg)

    monkeypatch.setattr("keyboard_logger.append_debug", fake_debug)
    logger = DummyLogger(log_path, summary_path, log_mode=True)
    called = []
    original_finish = logger._finish_word

    def intercept(*args, **kwargs):
        called.append(True)
        return original_finish(*args, **kwargs)

    logger._finish_word = intercept
    simulate_word(logger, "have")

    assert called
    assert "have" in logger.scored
    assert logger.summary["word_accuracy"]["correct"] >= 1
    assert any("Word 'have'" in msg for msg in messages)


def test_speed_point_awarded_for_fast_session(tmp_path: Path):
    speed_config = {
        "baseline_interval_ms": 320,
        "interval_pct_threshold": 90,
        "accuracy_pct_threshold": 80,
        "session_interval_gap_ms": 5000,
        "target_sessions": 5,
    }
    logger = make_logger_with_speed_config(tmp_path, speed_config)
    logger._track_session_interval(100)
    logger._track_session_interval(120)
    logger._score_session_word(True)
    logger._score_session_word(True)
    logger._commit_speed_session()

    points = logger.summary["speed_points"]
    assert points["earned"] == 1
    assert points["sessions"] == 1
    assert points["target_sessions"] == 5
    assert points["last_accuracy_pct"] == 100
    assert points["last_avg_interval"] == pytest.approx(110, rel=0.01)


def test_speed_point_blocked_when_accuracy_too_low(tmp_path: Path):
    speed_config = {
        "baseline_interval_ms": 320,
        "interval_pct_threshold": 90,
        "accuracy_pct_threshold": 100,
        "session_interval_gap_ms": 5000,
        "target_sessions": 5,
    }
    logger = make_logger_with_speed_config(tmp_path, speed_config)
    logger._track_session_interval(100)
    logger._score_session_word(False)
    logger._score_session_word(True)
    logger._commit_speed_session()

    points = logger.summary["speed_points"]
    assert points["earned"] == 0
    assert points["sessions"] == 1
    assert points["last_accuracy_pct"] == pytest.approx(50, rel=0.01)


def test_short_words_ignored_for_accuracy(tmp_path: Path):
    log_path = tmp_path / "keystrokes.jsonl"
    summary_path = tmp_path / "summary.json"
    logger = WrappedLogger(log_path, summary_path)
    initial = logger.summary["word_accuracy"]["correct"]
    assert not logger._score_word("cat")
    assert logger.summary["word_accuracy"]["correct"] == initial


def test_speed_points_increment_single_per_session(tmp_path: Path):
    speed_config = {
        "baseline_interval_ms": 320,
        "interval_pct_threshold": 90,
        "accuracy_pct_threshold": 70,
        "session_interval_gap_ms": 5000,
        "target_sessions": 5,
    }
    logger = make_logger_with_speed_config(tmp_path, speed_config)
    logger._track_session_interval(100)
    logger._score_session_word(True)
    logger._commit_speed_session()
    logger._track_session_interval(100)
    logger._score_session_word(True)
    logger._commit_speed_session()

    points = logger.summary["speed_points"]
    assert points["earned"] == 2
    assert points["sessions"] == 2


def test_speed_session_logs_threshold(monkeypatch, tmp_path: Path):
    speed_config = {
        "baseline_interval_ms": 320,
        "interval_pct_threshold": 90,
        "accuracy_pct_threshold": 70,
        "session_interval_gap_ms": 5000,
        "target_sessions": 3,
    }
    messages = []

    def fake_debug(msg, _=None):
        messages.append(msg)

    monkeypatch.setenv("KEYBOARD_WRAPPED_ROOT", str(tmp_path))
    monkeypatch.setattr("keyboard_logger.append_debug", fake_debug)
    logger = make_logger_with_speed_config(tmp_path, speed_config)
    logger._track_session_interval(150)
    logger._score_session_word(True)
    logger._score_session_word(True)
    logger._commit_speed_session()
    assert any("Speed session" in msg for msg in messages)
    assert any("accuracy threshold" in msg for msg in messages)
