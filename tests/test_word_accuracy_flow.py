import json
from pathlib import Path

import pytest

from scripts.mock_keystrokes import inject_keys


def test_mock_injection_records_word_accuracy(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KEYBOARD_WRAPPED_ROOT", str(tmp_path))
    summary_path = tmp_path / "summary.json"
    keystroke_log = tmp_path / "keystrokes.jsonl"
    debug_log = tmp_path / "widget_debug.log"

    summary, events = inject_keys(
        keys=list("the"),
        summary_path=summary_path,
        keystroke_path=keystroke_log,
        debug_path=debug_log,
        interval_ms=100,
        duration_ms=70,
    )

    assert summary["word_accuracy"]["correct"] == 1
    assert summary["word_accuracy"]["score"] > 0

    persisted = json.loads(summary_path.read_text())
    assert persisted["word_accuracy"]["score"] == summary["word_accuracy"]["score"]
    log_text = debug_log.read_text()
    assert "Word 'the' earned" in log_text
