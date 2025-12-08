import json
from pathlib import Path

import pytest

from gpt_insights import (
    adjacency_summary,
    fallback_analysis,
    highlight_rage_day,
    highlight_word_day,
    keyboard_age_from_speed,
    load_json,
    summarize_word_shapes,
    summarize_key_holds,
    transition_summary,
)


SAMPLE_SUMMARY = Path("data/sample_summary.json")


def load_sample_summary():
    return load_json(SAMPLE_SUMMARY)


def test_highlight_rage_day_returns_peak():
    summary = load_sample_summary()
    peak = highlight_rage_day(summary)
    assert peak is not None, "Expected a rage peak entry when daily_rage has data"
    assert isinstance(peak[0], str)
    assert isinstance(peak[1], int)


def test_highlight_word_day_returns_feast():
    summary = load_sample_summary()
    feast = highlight_word_day(summary)
    assert feast is not None, "Expected a word feast record from daily_word_counts"
    assert feast["topWord"] is not None
    assert feast["total"] == sum(summary["daily_word_counts"][feast["date"]].values())


def test_fallback_analysis_mentions_sample_mode():
    summary = load_sample_summary()
    analysis = fallback_analysis(summary, sample_mode=True)
    assert "Offline sample" in analysis
    assert "Keyboard age" in analysis
    assert "Top words" in analysis


def test_sample_data_has_expected_keys():
    summary = load_sample_summary()
    keys = {"total_events", "daily_rage", "daily_word_counts"}
    assert keys.issubset(summary.keys())


def test_typing_profile_summary_present():
    summary = load_sample_summary()
    profile = summary.get("typing_profile")
    assert profile
    assert profile["avg_interval"] > 0
    assert profile["avg_press_length"] > 0
    assert profile["wpm"] > 0


def test_word_shapes_have_durations():
    summary = load_sample_summary()
    shapes = summary.get("word_shapes", {})
    assert shapes
    for word, records in shapes.items():
        assert records
        for record in records:
            assert "durations" in record
            assert all(isinstance(length, int) for length in record["durations"])


def test_keyboard_age_from_speed_bounds():
    summary = load_sample_summary()
    age = keyboard_age_from_speed(summary)
    assert 0.5 <= age <= 12


def test_transition_summary_contains_arrows():
    summary = load_sample_summary()
    transitions = transition_summary(summary, limit=3)
    assert transitions
    assert all("->" in item for item in transitions)


def test_adjacency_summary_produces_pairs():
    summary = load_sample_summary()
    adjacency = adjacency_summary(summary, limit=3)
    assert adjacency
    assert all("->" in item for item in adjacency)


def test_summarize_word_shapes_returns_notes():
    summary = load_sample_summary()
    notes = summarize_word_shapes(summary, limit=2)
    assert isinstance(notes, list)
    assert any("avg hold" in note for note in notes)


def test_summarize_key_holds_returns_sorted_rows():
    summary = load_sample_summary()
    holds = summarize_key_holds(summary, limit=3)
    assert len(holds) <= 3
    assert all(len(entry) == 3 for entry in holds)
    if len(holds) > 1:
        assert all(holds[i][1] >= holds[i + 1][1] for i in range(len(holds) - 1))
