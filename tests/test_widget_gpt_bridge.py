import json
from pathlib import Path

import pytest

from scripts import widget_gpt


def _make_paths(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    feed_path = data_dir / "widget_gpt_feed.json"
    state_path = data_dir / "widget_gpt_state.json"
    progress_path = data_dir / "widget_progress.json"
    debug_path = data_dir / "widget_debug.log"
    debug_path.write_text("")
    return progress_path, feed_path, state_path, debug_path


def _write_progress(path: Path):
    path.write_text(
        json.dumps(
            {
                "timestamp": 0,
                "keyProgress": 200,
                "speedProgress": 40,
                "handshakeProgress": 18,
            }
        )
    )


def test_widget_gpt_bridge_dry_run(tmp_path: Path):
    progress_path, feed_path, state_path, debug_path = _make_paths(tmp_path)
    _write_progress(progress_path)

    widget_gpt.main(
        [
            "--mode",
            "sample",
            "--root",
            str(tmp_path),
            "--once",
            "--dry-run",
        ]
    )

    assert feed_path.exists()
    assert state_path.exists()

    feed = json.loads(feed_path.read_text())
    assert feed["mode"] == "sample"
    assert "analysis_text" in feed
    assert feed["progress"]["keyProgress"] == 200

    state = json.loads(state_path.read_text())
    assert state["iteration"] == 1
    assert state["last_snapshot"]["keyProgress"] == 200
    assert debug_path.exists()


def test_widget_gpt_bridge_logs_prompt_and_response(tmp_path: Path, monkeypatch):
    progress_path, feed_path, state_path, debug_path = _make_paths(tmp_path)
    _write_progress(progress_path)

    response_text = "Fresh insight!"

    def fake_call(prompt, config):
        return response_text

    monkeypatch.setattr(widget_gpt, "call_openai", fake_call)
    config = {"gpt": {"model": "gpt-4o-mini", "temperature": 0.1}}

    result = widget_gpt.run_cycle(
        progress_path,
        feed_path,
        state_path,
        debug_path,
        config,
        "real",
        dry_run=False,
        root=tmp_path,
    )

    assert result is True
    assert feed_path.exists()
    feed = json.loads(feed_path.read_text())
    assert feed["analysis_text"] == response_text
    log_content = debug_path.read_text()
    assert "GPT prompt (mode real, iteration 1)" in log_content
    assert "GPT response (iteration 1, mode real)" in log_content


def test_widget_gpt_bridge_logs_error_and_fallback(tmp_path: Path, monkeypatch):
    progress_path, feed_path, state_path, debug_path = _make_paths(tmp_path)
    _write_progress(progress_path)

    def failing_call(prompt, config):
        raise RuntimeError("boom")

    monkeypatch.setattr(widget_gpt, "call_openai", failing_call)

    config = {"gpt": {"model": "gpt-4o-mini", "temperature": 0.1}}

    result = widget_gpt.run_cycle(
        progress_path,
        feed_path,
        state_path,
        debug_path,
        config,
        "real",
        dry_run=False,
        root=tmp_path,
    )

    assert result is True
    feed = json.loads(feed_path.read_text())
    assert "[real] iteration 1" in feed["analysis_text"]
    log_content = debug_path.read_text()
    assert "GPT prompt (mode real, iteration 1)" in log_content
    assert "GPT request error (iteration 1, mode real)" in log_content
