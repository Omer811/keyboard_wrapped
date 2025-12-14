from pathlib import Path

import json
import pytest

from scripts import widget_refresh


@pytest.fixture
def sample_summary(tmp_path: Path) -> Path:
    source = Path("data/sample_summary.json")
    dest = tmp_path / "summary.json"
    dest.write_text(source.read_text())
    return dest


def test_persist_widget_progress_updates(tmp_path: Path, sample_summary: Path):
    output = tmp_path / "widget_progress.json"
    original_snapshot = widget_refresh.persist_widget_progress(sample_summary, output)

    assert output.exists()
    assert isinstance(original_snapshot["keyProgress"], float)
    assert output.read_text()

    summary_data = json.loads(sample_summary.read_text())
    summary_data["total_events"] = 9999
    summary_data["typing_profile"]["avg_interval"] = 190
    sample_summary.write_text(json.dumps(summary_data))

    orig_mtime = output.stat().st_mtime
    updated_snapshot = widget_refresh.persist_widget_progress(sample_summary, output)
    assert updated_snapshot["keyProgress"] == 9999.0
    assert output.stat().st_mtime > orig_mtime
    assert "wordAccuracyScore" in updated_snapshot
    assert "wordAccuracyTarget" in updated_snapshot


def test_sample_adjustment_scales_down():
    summary = {
        "total_events": 2000,
        "letters": 1500,
        "actions": 200,
        "words": 800,
        "rage_clicks": 40,
        "long_pauses": 12,
        "typing_profile": {"avg_interval": 400},
    }
    settings = {"sample_total_ratio": 0.1, "sample_avg_interval": 150}
    adjusted = widget_refresh.apply_sample_adjustments(summary, settings)
    assert adjusted["total_events"] == 200
    assert adjusted["letters"] == 150
    assert adjusted["typing_profile"]["avg_interval"] == 150


def test_accuracy_score_is_clamped(tmp_path: Path, sample_summary: Path):
    output = tmp_path / "widget_progress.json"
    summary_data = json.loads(sample_summary.read_text())
    summary_data.setdefault("word_accuracy", {})["score"] = -42
    sample_summary.write_text(json.dumps(summary_data))
    over_score = widget_refresh.persist_widget_progress(sample_summary, output)
    assert over_score["wordAccuracyScore"] == 0

    target = widget_refresh.load_widget_settings()["accuracy_target"]
    summary_data["word_accuracy"]["score"] = target + 45
    sample_summary.write_text(json.dumps(summary_data))
    high_score = widget_refresh.persist_widget_progress(sample_summary, output)
    assert high_score["wordAccuracyScore"] == pytest.approx(target)
