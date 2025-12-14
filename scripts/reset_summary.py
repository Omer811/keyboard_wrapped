import argparse
import json
from pathlib import Path


DEFAULT_SUMMARY = {
    "daily_activity": {},
    "daily_rage": {},
    "daily_word_counts": {},
    "rage_clicks": 0,
    "long_pauses": 0,
    "daily_word_counts": {},
    "total_events": 0,
}


def load_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_summary(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def reset_daily(path: Path):
    summary = load_summary(path)
    for field in [
        "daily_activity",
        "daily_word_counts",
        "daily_rage",
        "rage_clicks",
        "long_pauses",
        "key_counts",
        "interval_stats",
    ]:
        if field in summary:
            value = summary[field]
            if isinstance(value, dict):
                value.clear()
            elif isinstance(value, (int, float)):
                summary[field] = 0
    summary["daily_activity"] = {}
    summary["daily_word_counts"] = {}
    summary["daily_rage"] = {}
    summary.setdefault("word_accuracy", {"score": 0, "correct": 0, "incorrect": 0})
    summary["word_accuracy"].update({"score": 0, "correct": 0, "incorrect": 0})
    write_summary(path, summary)


def main():
    parser = argparse.ArgumentParser(description="Reset per-day keyboard stats for demos.")
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/summary.json"),
        help="Summary file to update.",
    )
    args = parser.parse_args()
    reset_daily(args.summary)
    print(f"Daily stats reset for {args.summary}")


if __name__ == "__main__":
    main()
