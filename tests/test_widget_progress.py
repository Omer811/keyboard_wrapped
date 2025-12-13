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
