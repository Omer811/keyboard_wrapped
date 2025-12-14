
from pathlib import Path

import pytest
from pynput import keyboard

from keyboard_logger import WrappedLogger


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
    simulate_word(logger, "the")

    assert called
    assert "the" in logger.scored
    assert logger.summary["word_accuracy"]["correct"] >= 1
    assert any("Word 'the'" in msg for msg in messages)
