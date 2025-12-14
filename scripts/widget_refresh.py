import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

ASCII_LAYOUT = list("qwertyuiopasdfghjklzxcvbnm")

from scripts.configuration import load_widget_settings


def load_summary(path: Path) -> Dict[str, Any]:
    text = path.read_text()
    return json.loads(text)


def apply_sample_adjustments(
    summary: Dict[str, Any], settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    settings = settings or load_widget_settings()
    ratio = max(0.0, min(1.0, settings.get("sample_total_ratio", 0.05)))
    scaled_keys = ["total_events", "letters", "actions", "words", "rage_clicks", "long_pauses"]
    adjusted = dict(summary)
    for key in scaled_keys:
        value = summary.get(key)
        if isinstance(value, (int, float)):
            adjusted[key] = max(1, int(round(value * ratio)))
    if isinstance(adjusted.get("typing_profile"), dict):
        typing = dict(adjusted["typing_profile"])
    else:
        typing = {}
    typing["avg_interval"] = float(settings.get("sample_avg_interval", 210))
    adjusted["typing_profile"] = typing
    return adjusted


def compute_speed_score(avg_interval_ms: float) -> float:
    return min(120.0, 60000.0 / avg_interval_ms) if avg_interval_ms > 0 else 0.0


def compute_handshake(summary: Dict[str, Any], threshold: float, speed_ref: float) -> float:
    key_pairs = summary.get("key_pairs", {})
    score = 0
    for src, targets in key_pairs.items():
        src_index = None
        if src:
            c = src[0].lower()
            if c in ASCII_LAYOUT:
                src_index = ASCII_LAYOUT.index(c)
        if src_index is None:
            continue
        for dst, count in targets.items():
            dst_index = None
            if dst:
                c2 = dst[0].lower()
                if c2 in ASCII_LAYOUT:
                    dst_index = ASCII_LAYOUT.index(c2)
            if dst_index is None:
                continue
            if abs(src_index - dst_index) >= 4 and (speed_ref < threshold or speed_ref == 0):
                score += count
    return float(min(score, 80))


def build_snapshot(summary: Dict[str, Any]) -> Dict[str, Any]:
    total_keys = float(summary.get("total_events", 0))
    typing_profile = summary.get("typing_profile", {})
    avg_interval = float(typing_profile.get("avg_interval", 0))
    speed_score = compute_speed_score(avg_interval)
    handshake = compute_handshake(summary, threshold=250.0, speed_ref=avg_interval)

    return {
        "timestamp": int(time.time()),
        "keyProgress": total_keys,
        "keyTarget": 5000,
        "speedProgress": speed_score,
        "speedTarget": 120,
        "handshakeProgress": handshake,
        "handshakeTarget": 80,
    }


def _clamp_accuracy_score(score: float, target: float) -> float:
    return max(0.0, min(score, target))


def persist_widget_progress(
    summary_path: Path, progress_path: Path, mode: str = "real"
) -> Dict[str, Any]:
    summary = load_summary(summary_path)
    if mode == "sample":
        summary = apply_sample_adjustments(summary)
    snapshot = build_snapshot(summary)
    accuracy_settings = load_widget_settings()
    accuracy_summary = summary.get("word_accuracy", {})
    target = float(accuracy_settings["accuracy_target"])
    raw_score = float(accuracy_summary.get("score", 0))
    snapshot["wordAccuracyScore"] = _clamp_accuracy_score(raw_score, target)
    snapshot["wordAccuracyTarget"] = target
    progress_path.write_text(json.dumps(snapshot, indent=2))
    return snapshot
