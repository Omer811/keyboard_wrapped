import json
import time
from pathlib import Path
from typing import Any, Dict


ASCII_LAYOUT = list("qwertyuiopasdfghjklzxcvbnm")


def load_summary(path: Path) -> Dict[str, Any]:
    text = path.read_text()
    return json.loads(text)


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


def persist_widget_progress(summary_path: Path, progress_path: Path) -> Dict[str, Any]:
    summary = load_summary(summary_path)
    snapshot = build_snapshot(summary)
    progress_path.write_text(json.dumps(snapshot, indent=2))
    return snapshot
