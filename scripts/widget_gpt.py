import argparse
import hashlib
import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.configuration import load_app_config as load_config, widget_paths
from scripts.logger_health import append_debug

try:
    from gpt_insights import call_openai
except ModuleNotFoundError as exc:
    DEBUG_LOG = REPO_ROOT / "data" / "widget_debug.log"
    DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with DEBUG_LOG.open("a", encoding="utf-8") as fh:
        fh.write(
            f"{timestamp} widget_gpt import error: {exc}. "
            "Please ensure gpt_insights.py is discoverable.\n"
        )
    raise


DEFAULT_POLL = 4.0

DEFAULT_RING_PROMPT_TEMPLATE = textwrap.dedent(
    """\
You are KeyboardAI for the menu bar. Mode: {mode}. Progress: {keyProgress}/{keyTarget} strokes, {speedProgress}/{speedTarget} speed points, handshake {handshakeProgress}/{handshakeTarget}, accuracy {wordAccuracyScore}/{wordAccuracyTarget}.
Changes: {diff_text}.
Offer a single encouraging sentence that nudges the user toward the next milestone.
"""
)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def snapshot_hash(snapshot: Dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def describe_diff(
    current: Dict[str, Any], previous: Dict[str, Any]
) -> List[str]:
    diffs = []
    mapping = [
        ("keyProgress", "Keystrokes"),
        ("speedProgress", "Speed points"),
        ("handshakeProgress", "Keyboard balance"),
    ]
    for key, label in mapping:
        current_value = float(current.get(key, 0))
        prev_value = float(previous.get(key, 0))
        delta = current_value - prev_value
        if abs(delta) < 0.5:
            continue
        direction = "up" if delta > 0 else "down"
        diffs.append(f"{label} {direction} {abs(delta):.0f}")
    return diffs


def build_ring_prompt(
    snapshot: Dict[str, Any],
    diff_lines: List[str],
    mode: str,
    template: str,
) -> str:
    context = {
        "mode": mode,
        "keyProgress": snapshot.get("keyProgress", 0),
        "keyTarget": snapshot.get("keyTarget", 5000),
        "speedProgress": int(snapshot.get("speedProgress", 0)),
        "speedTarget": snapshot.get("speedTarget", 120),
        "handshakeProgress": int(snapshot.get("handshakeProgress", 0)),
        "handshakeTarget": snapshot.get("handshakeTarget", 80),
        "wordAccuracyScore": snapshot.get("wordAccuracyScore", 0),
        "wordAccuracyTarget": snapshot.get("wordAccuracyTarget", 120),
        "diff_text": "; ".join(diff_lines) or "steady rhythm",
    }
    try:
        return template.format(**context)
    except Exception:
        return template


def fallback_message(
    snapshot: Dict[str, Any], diff_lines: List[str], mode: str, iteration: int
) -> str:
    diff_text = diff_lines[0] if diff_lines else "steady rhythm"
    return (
        f"[{mode}] iteration {iteration}: {diff_text}. "
        f"Key strokes {int(snapshot.get('keyProgress', 0))}, "
        f"Speed {int(snapshot.get('speedProgress', 0))}, "
        f"Balance {int(snapshot.get('handshakeProgress', 0))}."
    )


def run_cycle(
    progress_path: Path,
    feed_path: Path,
    state_path: Path,
    debug_path: Path,
    config: Dict[str, Any],
    mode: str,
    dry_run: bool,
) -> bool:
    if not progress_path.exists():
        return False
    snapshot = load_json(progress_path)
    current_hash = snapshot_hash(snapshot)
    state = {}
    if state_path.exists():
        state = load_json(state_path)
    previous_snapshot = state.get("last_snapshot", {})
    diff_lines = describe_diff(snapshot, previous_snapshot)
    iteration = int(state.get("iteration", 0)) + 1
    prompt_template = config.get("gpt", {}).get("ring_prompt_template") or DEFAULT_RING_PROMPT_TEMPLATE
    prompt = build_ring_prompt(snapshot, diff_lines, mode, prompt_template)
    diff_summary = "; ".join(diff_lines) if diff_lines else "steady rhythm"
    prompt += (
        f"\nStats delta since the last insight: {diff_summary}. "
        "Feel free to reference the change when crafting encouragement."
    )
    message = fallback_message(snapshot, diff_lines, mode, iteration)
    append_debug(
        f"GPT prompt (mode {mode}, iteration {iteration}): {prompt[:400].replace(os.linesep, ' ')}",
        debug_path,
    )
    if not dry_run:
        try:
            message = call_openai(prompt, config)
            append_debug(
                f"GPT response (iteration {iteration}, mode {mode}): {message[:400].replace(os.linesep, ' ')}",
                debug_path,
            )
        except Exception as exc:  # pragma: no cover
            print(f"GPT bridge request failed: {exc}", file=sys.stderr)
            print("Falling back to local message.", file=sys.stderr)
            append_debug(
                f"GPT request error (iteration {iteration}, mode {mode}): {exc}",
                debug_path,
            )
    write_json(
        feed_path,
        {
            "timestamp": int(time.time()),
            "mode": mode,
            "iteration": iteration,
            "analysis_text": message,
            "diff": diff_lines,
            "diff_summary": diff_summary,
            "progress": snapshot,
        },
    )
    write_json(
        state_path,
        {
            "last_hash": current_hash,
            "last_snapshot": snapshot,
            "iteration": iteration,
        },
    )
    return True


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="Bridge widget progress to GPT.")
    parser.add_argument("--mode", choices=["real", "sample"], default="real")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interval", type=float, default=DEFAULT_POLL)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    config = load_config(root)
    paths = widget_paths(root, config)

    def cycle():
        return run_cycle(
            paths["progress"],
            paths["gpt_feed"],
            paths["gpt_state"],
            paths["debug"],
            config,
            args.mode,
            args.dry_run,
        )

    if args.once:
        cycle()
        return

    while True:
        try:
            cycle()
        except Exception as exc:  # pragma: no cover
            print(f"Widget GPT bridge error: {exc}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
