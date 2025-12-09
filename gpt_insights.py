import argparse
import hashlib
import json
import os
import textwrap
from pathlib import Path
from typing import Any, Dict

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None

CONFIG_PATH = Path("config/app.json")
DEFAULT_SUMMARY = Path("data/summary.json")
DEFAULT_SAMPLE_SUMMARY = Path("data/sample_summary.json")
DEFAULT_OUTPUT = Path("data/gpt_insights.json")
DEFAULT_SAMPLE_OUTPUT = Path("data/sample_gpt_insight.json")


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return load_json(CONFIG_PATH)


def resolve_paths(config: Dict[str, Any], mode: str) -> Dict[str, Path]:
    data = config.get("data", {})
    summary_path = Path(
        data.get(
            f"{mode}_summary",
            str(DEFAULT_SAMPLE_SUMMARY if mode == "sample" else DEFAULT_SUMMARY),
        )
    )
    output_path = Path(
        data.get(
            f"{mode}_gpt",
            str(DEFAULT_SAMPLE_OUTPUT if mode == "sample" else DEFAULT_OUTPUT),
        )
    )
    return {"summary": summary_path, "output": output_path}


def summary_hash(summary: Dict[str, Any]) -> str:
    payload = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def insight_meta_path(output_path: Path) -> Path:
    return output_path.with_suffix(output_path.suffix + ".meta")


def load_meta(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def write_meta(path: Path, summary_hash_value: str, success: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "summary_hash": summary_hash_value,
                "last_success": success,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )


def top_words(summary: Dict[str, Any], limit=5):
    entries = sorted(
        summary.get("word_counts", {}).items(), key=lambda item: item[1], reverse=True
    )
    return entries[:limit]


def fastest_words(summary: Dict[str, Any], limit=5):
    durations = summary.get("word_durations", {})
    averages = []
    for word, stats in durations.items():
        count = stats.get("count", 0)
        total = stats.get("total_ms", 0)
        if count:
            averages.append((word, total / count))
    averages.sort(key=lambda item: item[1])
    return [(word, round(avg)) for word, avg in averages[:limit]]


def highlight_rage_day(summary: Dict[str, Any]):
    entries = list(summary.get("daily_rage", {}).items())
    if not entries:
        return None
    return max(entries, key=lambda item: item[1])


def highlight_word_day(summary: Dict[str, Any]):
    entries = list(summary.get("daily_word_counts", {}).items())
    best = {"date": None, "total": 0, "topWord": None, "topValue": 0}
    for date, counts in entries:
        total = sum(counts.values())
        if not counts:
            continue
        word, value = max(counts.items(), key=lambda item: item[1])
        if total > best["total"]:
            best = {"date": date, "total": total, "topWord": word, "topValue": value}
    return best["date"] and best


def typing_profile(summary: Dict[str, Any]) -> Dict[str, float]:
    profile = summary.get("typing_profile", {})
    interval_stats = summary.get("interval_stats", {})
    avg_interval = profile.get("avg_interval")
    if not avg_interval and interval_stats.get("count"):
        avg_interval = interval_stats["total_ms"] / interval_stats["count"]
    avg_press_length = profile.get("avg_press_length")
    if not avg_press_length:
        lengths = summary.get("key_press_lengths", {})
        total_ms = sum(entry.get("total_ms", 0) for entry in lengths.values())
        count = sum(entry.get("count", 0) for entry in lengths.values())
        avg_press_length = total_ms / count if count else 0
    wpm = profile.get("wpm")
    if not wpm and avg_interval:
        wpm = 60000 / avg_interval
    long_pause_rate = profile.get("long_pause_rate", 0)
    return {
        "avg_interval": round(avg_interval or 0, 1),
        "avg_press_length": round(avg_press_length or 0, 1),
        "wpm": round(wpm or 0, 1),
        "long_pause_rate": round(long_pause_rate or 0, 3),
    }


def summarize_key_holds(summary: Dict[str, Any], limit=4):
    entries = summary.get("key_press_lengths", {})
    key_info = []
    for key, stats in entries.items():
        count = stats.get("count", 0)
        total = stats.get("total_ms", 0)
        if not count:
            continue
        average = total / count
        key_info.append((key, average, count))
    key_info.sort(key=lambda item: item[1], reverse=True)
    return key_info[:limit]


def format_key_hold_summary(key_holds):
    if not key_holds:
        return "No dwell data yet."
    return ", ".join(
        f"{key.upper()} {round(avg)}ms over {count} hits"
        for key, avg, count in key_holds
    )


def keyboard_age_from_speed(summary: Dict[str, Any]) -> float:
    profile = typing_profile(summary)
    wpm = profile["wpm"]
    interval = profile["avg_interval"] or 500
    press = profile["avg_press_length"] or 200
    score = (wpm / 120) * 3 + (500 / max(interval, 1)) * 1.5 + (200 / max(press, 1))
    return round(max(0.5, min(12, score)), 1)


def summarize_word_shapes(summary: Dict[str, Any], limit=3):
    shapes = summary.get("word_shapes", {})
    entries = top_words(summary, limit=limit)
    results = []
    for word, _ in entries:
        records = shapes.get(word, [])
        if not records:
            continue
        length = len(word)
        totals = [0] * length
        counts = [0] * length
        for record in records:
            for idx, duration in enumerate(record.get("durations", [])):
                if idx >= length:
                    break
                totals[idx] += duration or 0
                counts[idx] += 1
        averages = [
            totals[idx] // counts[idx] if counts[idx] else 0 for idx in range(length)
        ]
        avg_hold = round(sum(averages) / length) if length else 0
        results.append(f"{word} avg hold {avg_hold}ms across {len(records)} runs")
    return results


def transition_summary(summary: Dict[str, Any], limit=5):
    merged = []
    for frm, nexts in summary.get("word_pairs", {}).items():
        for to, count in nexts.items():
            merged.append((count, frm, to))
    merged.sort(reverse=True)
    return [f"{frm}->{to} ({count})" for count, frm, to in merged[:limit]]


def adjacency_summary(summary: Dict[str, Any], limit=5):
    merged = []
    for frm, nexts in summary.get("key_pairs", {}).items():
        for to, count in nexts.items():
            merged.append((count, frm, to))
    merged.sort(reverse=True)
    return [f"{frm}->{to} ({count})" for count, frm, to in merged[:limit]]


def build_prompt(summary: Dict[str, Any]):
    age = keyboard_age_from_speed(summary)
    top = top_words(summary)
    fastest = fastest_words(summary)
    rage = highlight_rage_day(summary)
    word_day = highlight_word_day(summary)

    pairs = []
    for from_word, nexts in summary.get("word_pairs", {}).items():
        sorted_next = sorted(nexts.items(), key=lambda item: item[1], reverse=True)
        if sorted_next:
            pairs.append(f"{from_word}->{sorted_next[0][0]}")
    pairs = pairs[:3]

    typing = typing_profile(summary)
    shapes = summarize_word_shapes(summary, limit=4)
    transitions = transition_summary(summary, limit=4)
    adjacencies = adjacency_summary(summary, limit=4)
    key_holds = summarize_key_holds(summary, limit=4)
    hold_text = format_key_hold_summary(key_holds)
    prompt = textwrap.dedent(
        f"""\
        You are KeyboardAI. Analyze the following keyboard summary data and respond with JSON only.
        Address the user directly using "you" (no references to "the writer" or third-person). Keep the response insightful and playful—fun but sharp.
        Provide an "analysis_text" string and an "insights" array.
        Each insight must have "tag", "title", "body" covering:
        - A persona label and why you call the typist that.
        - A keyboard age estimate described humorously, referencing speed/presses/pauses.
        - Tempo notes (wpm, intervals, long holds) describing how it feels to type like you do.
        - Favorite words with quick commentary and the vibe they create for you.
        - Fastest words with durations, standout days, and layout thoughts for your most fluent transitions.

        Return valid JSON only and keep it double-quoted. No markdown wrappers.

        Total presses: {summary.get('total_events')}
        Letters: {summary.get('letters')}, Actions: {summary.get('actions')}
        Rage bursts: {summary.get('rage_clicks')} (daily high {rage[1] if rage else 0})
        Word highlights: {', '.join(word for word, _ in top[:3])}
        Fastest words: {', '.join(f"{word} ({duration}ms)" for word, duration in fastest)}
        Word pairs: top sequences {', '.join(pairs)}
        Word day: {word_day['date'] if word_day else '—'} (top word {word_day['topWord'] if word_day else '—'})
        Typing speed: {typing['wpm']} wpm, avg interval {typing['avg_interval']}ms, avg press {typing['avg_press_length']}ms, long pause rate {typing['long_pause_rate'] * 100:.1f}%.
        Word shapes: {', '.join(shapes) if shapes else '—'}
        Word transitions: {', '.join(transitions) if transitions else '—'}
        Key adjacency: {', '.join(adjacencies) if adjacencies else '—'}
        Key dwellers: {hold_text}
        Keyboard interface story: Sketch a vivid narrative of how you physically engage the keyboard, leaning on dwell stats and rhythm.
        """
    )
    return prompt


def fallback_analysis(summary: Dict[str, Any], sample_mode=False):
    age = keyboard_age_from_speed(summary)
    typing = typing_profile(summary)
    top = ", ".join(word for word, _ in top_words(summary, limit=3)) or "—"
    fast = ", ".join(word for word, _ in fastest_words(summary, limit=3)) or "—"
    rage = highlight_rage_day(summary)
    word_day = highlight_word_day(summary)
    parts = [
        f"Keyboard age: {age} years, with {typing['wpm']} WPM, {typing['avg_interval']}ms median pauses, and {typing['avg_press_length']}ms key holds.",
        f"Keyboard age reasoning: {typing['wpm']} WPM speed, {typing['avg_press_length']}ms holds, and {typing['long_pause_rate'] * 100:.1f}% long pauses lock in this age, together with signature words of {top}.",
        f"Top words: {top}.",
        f"Fastest words: {fast}.",
        f"Long pauses strike at roughly {typing['long_pause_rate'] * 100:.1f}% of presses.",
    ]
    shape_notes = summarize_word_shapes(summary, limit=2)
    if shape_notes:
        parts.append(f"Word shapes: {', '.join(shape_notes)}.")
    transition_notes = transition_summary(summary, limit=2)
    if transition_notes:
        parts.append(f"Top transitions: {', '.join(transition_notes)}.")
    hold_notes = summarize_key_holds(summary, limit=2)
    if hold_notes:
        parts.append(f"Key dwellers: {format_key_hold_summary(hold_notes)}.")
    if rage:
        parts.append(f"Rage peak on {rage[0]} with {rage[1]} bursts.")
    if word_day:
        parts.append(
            f"Word feast on {word_day['date']} with {word_day['topWord']} {word_day['topValue']} times."
        )
    if sample_mode:
        parts.append("Offline sample insight keeps the AI cube populated.")
    return " ".join(parts)


def fallback_structured(summary: Dict[str, Any], sample_mode=False):
    analysis_text = fallback_analysis(summary, sample_mode=sample_mode)
    insights = [
        persona_insight_card(summary),
        keyboard_age_card(summary),
        tempo_card(summary),
        vocabulary_card(summary),
        rhythm_card(summary),
    ]
    return {"analysis_text": analysis_text, "insights": insights}


def persona_insight_card(summary: Dict[str, Any]):
    total = max(summary.get("total_events", 1), 1)
    letter_ratio = summary.get("letters", 0) / total
    rage_ratio = summary.get("rage_clicks", 0) / total
    word_counts = summary.get("word_counts", {})
    signature = (
        max(word_counts.items(), key=lambda item: item[1])[0]
        if word_counts
        else "your cadence"
    )
    if rage_ratio > 0.02:
        title = "Blazing Editor"
        body = f"Rapid edits stand out while \"{signature}\" anchors your tempo spikes."
    elif letter_ratio > 0.85:
        title = "Midnight Wordsmith"
        body = f"Long-form letters dominate and \"{signature}\" is your poetic motif."
    elif summary.get("actions", 0) / total > 0.35:
        title = "Navigator"
        body = f"Modifiers and navigation keys stay busy while \"{signature}\" steadies your path."
    else:
        title = "Steady Storyteller"
        body = f"`{signature}` keeps your balanced sessions resilient."
    return {"tag": "Persona", "title": title, "body": body}


def keyboard_age_card(summary: Dict[str, Any]):
    age = keyboard_age_from_speed(summary)
    typing = typing_profile(summary)
    return {
        "tag": "Keyboard age",
        "title": f"{age} years",
        "body": (
            f"Speed {typing['wpm']} WPM, {typing['avg_interval']}ms pauses, "
            f"and {typing['avg_press_length']}ms holds support this age."
        ),
    }


def tempo_card(summary: Dict[str, Any]):
    typing = typing_profile(summary)
    return {
        "tag": "Tempo",
        "title": f"{typing['wpm']} WPM rhythm",
        "body": (
            f"Long pause rate is {typing['long_pause_rate'] * 100:.1f}% while spells stay compact "
            f"({typing['avg_press_length']}ms) for fluent typing."
        ),
    }


def vocabulary_card(summary: Dict[str, Any]):
    top = top_words(summary, limit=3)
    words = ", ".join(word for word, _ in top) or "No words yet"
    return {
        "tag": "Vocabulary",
        "title": "Top words",
        "body": f"{words} define your narrative and signal what your keyboard loves.",
    }


def rhythm_card(summary: Dict[str, Any]):
    rage = highlight_rage_day(summary)
    word_day = highlight_word_day(summary)
    parts = []
    if rage:
        parts.append(f"Rage peak on {rage[0]} with {rage[1]} bursts.")
    if word_day:
        parts.append(f"{word_day['date']} featured {word_day['topWord']} {word_day['topValue']} times.")
    body = " ".join(parts) if parts else "No standout rhythms yet."
    return {"tag": "Rhythm", "title": "Rhythm story", "body": body}


def write_insight(text: str, structured: Dict[str, Any], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"analysis_text": text}
    if structured:
        payload["structured"] = structured
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def call_openai(prompt: str, config: Dict[str, Any]):
    if openai is None:
        raise ImportError("Install openai (`pip install openai`) to request GPT responses.")
    gpt_cfg = config.get("gpt", {})
    api_key = gpt_cfg.get("api_key") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No OpenAI API key found in config.")

    if openai_supports_new_api():
        client_cls = getattr(openai, "OpenAI", None)
        if client_cls is None:
            raise ValueError("Unable to instantiate OpenAI client for the installed SDK.")
        client = client_cls(api_key=api_key)
        response = client.chat.completions.create(
            model=gpt_cfg.get("model", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a keyboard analyst; be concise and insightful.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=gpt_cfg.get("temperature", 0.4),
        )
        return response.choices[0].message.content

    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model=gpt_cfg.get("model", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": "You are a keyboard analyst; be concise and insightful.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=gpt_cfg.get("temperature", 0.4),
    )
    return response.choices[0].message.content


def openai_supports_new_api():
    ver = getattr(openai, "__version__", "")
    if not ver:
        return False
    try:
        major = int(ver.split(".")[0])
        return major >= 1
    except ValueError:
        return False


def parse_structured_response(text: str) -> Dict[str, Any]:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return {}


def run():
    parser = argparse.ArgumentParser(description="Generate AI insight for keyboard stats.")
    parser.add_argument("--mode", choices=["real", "sample"], help="Override the configured data mode.")
    parser.add_argument("--summary", type=Path, help="Explicit summary file to read.")
    parser.add_argument("--output", type=Path, help="Where to write the AI insight JSON.")
    parser.add_argument("--netlify", action="store_true", help="(ignored) compatibility hook for `run_gpt_ui.sh --netlify`.")
    args = parser.parse_args()

    config = load_config()
    config_mode = config.get("mode", "real")
    mode = args.mode or config_mode
    paths = resolve_paths(config, mode)
    summary_path = args.summary or paths["summary"]
    if not summary_path.exists():
        raise FileNotFoundError(
            f"Summary {summary_path} missing; run the logger or switch the config mode."
        )
    output_path = args.output or paths["output"]
    summary = load_json(summary_path)
    summary_hash_value = summary_hash(summary)
    meta_path = insight_meta_path(output_path)
    existing_meta = load_meta(meta_path)
    if (
        existing_meta.get("summary_hash") == summary_hash_value
        and existing_meta.get("last_success")
        and output_path.exists()
    ):
        print(
            f"Summary unchanged ({summary_hash_value}); skipping GPT call and using existing insight."
        )
        return

    gpt_config = config.get("gpt", {})
    api_key = gpt_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
    structured = {}
    if not api_key:
        text = fallback_analysis(summary, sample_mode=(mode == "sample"))
        structured = fallback_structured(summary, sample_mode=(mode == "sample"))
        write_insight(text, structured, output_path)
        write_meta(meta_path, summary_hash_value, success=False)
        print(f"Wrote fallback insight to {output_path}")
        print("  (No OpenAI API key configured; fallback insight generated from local heuristics.)")
        return

    prompt = build_prompt(summary)
    print(f"GPT request stats: prompt {len(prompt)} chars, {len(prompt.encode('utf-8'))} bytes; summary has {len(json.dumps(summary))} chars")
    try:
        raw = call_openai(prompt, config)
        structured = parse_structured_response(raw)
        analysis_text = structured.get("analysis_text") or raw
    except Exception as exc:
        err_msg = getattr(exc, "args", None)
        print(f"OpenAI request failed: {exc}")
        print(f"OpenAI error payload: {err_msg}")
        analysis_text = fallback_analysis(summary)
        structured = fallback_structured(summary, sample_mode=(mode == "sample"))
        success = False
        print("Generated fallback insight because the OpenAI request did not succeed.")
    else:
        success = True

    write_insight(analysis_text, structured, output_path)
    write_meta(meta_path, summary_hash_value, success=success)
    print(f"Wrote AI insight to {output_path}")


if __name__ == "__main__":
    run()
