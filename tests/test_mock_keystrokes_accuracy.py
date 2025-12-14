import json
from pathlib import Path

from scripts.mock_keystrokes import inject_keys


def test_mock_keystrokes_logs_scored_words(tmp_path: Path):
    summary_path = tmp_path / "summary.json"
    keystroke_log = tmp_path / "keystrokes.jsonl"
    debug_log = tmp_path / "widget_debug.log"

    inject_keys(
        keys=list("hey there "),
        summary_path=summary_path,
        keystroke_path=keystroke_log,
        debug_path=debug_log,
        interval_ms=120,
        duration_ms=60,
    )

    log_text = debug_log.read_text()
    assert "Word 'heythere' earned" in log_text
    data = json.loads(summary_path.read_text())
    assert data["word_accuracy"]["incorrect"] >= 1
