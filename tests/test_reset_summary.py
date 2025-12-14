from pathlib import Path

import json


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

    from scripts.reset_summary import reset_daily

    reset_daily(path)
    updated = json.loads(path.read_text())
    assert updated["daily_activity"] == {}
    assert updated["daily_word_counts"] == {}
    assert updated["daily_rage"] == {}
    assert updated["rage_clicks"] == 0
    assert updated["long_pauses"] == 0
    assert updated["key_counts"] == {}
    assert updated["word_accuracy"]["score"] == 0
