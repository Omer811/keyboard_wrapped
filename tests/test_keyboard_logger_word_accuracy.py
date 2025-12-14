from pathlib import Path

import pytest

from keyboard_logger import WrappedLogger


def test_score_word_updates_summary(tmp_path: Path, monkeypatch):
    log_path = tmp_path / "keystrokes.jsonl"
    summary_path = tmp_path / "summary.json"
    messages = []

    def fake_debug(msg, _=None):
        messages.append(msg)

    monkeypatch.setattr("keyboard_logger.append_debug", fake_debug)
    logger = WrappedLogger(log_path, summary_path, log_mode=True)
    logger.summary["word_accuracy"] = {"score": 0, "correct": 0, "incorrect": 0}
    logger._score_word("the")

    assert logger.summary["word_accuracy"]["correct"] == 1
    assert logger.summary["word_accuracy"]["score"] >= 0
    assert any("Word 'the'" in msg for msg in messages)
