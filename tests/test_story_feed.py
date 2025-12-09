import json
from pathlib import Path

SAMPLE_INSIGHT = Path("data/sample_gpt_insight.json")


def load_sample_insight():
    with open(SAMPLE_INSIGHT, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_sample_insight_structured():
    payload = load_sample_insight()
    structured = payload.get("structured")
    assert isinstance(structured, dict), "Structured data must be present"
    insights = structured.get("insights")
    assert isinstance(insights, list), "Insights array required"
    assert insights, "Insights should not be empty"
    assert all("tag" in item and "title" in item and "body" in item for item in insights)
