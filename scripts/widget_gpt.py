import argparse
import hashlib
import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from scripts.configuration import load_app_config as load_config, widget_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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


def build_prompt(
    current: Dict[str, Any],
    diff_lines: List[str],
    iteration: int,
    mode: str,
) -> str:
    status = "live" if mode == "real" else "sample"
    diff_text = "; ".join(diff_lines) or "steady rhythm"
    return textwrap.dedent(
        f"""\
        You are KeyboardAI. The widget just refreshed (iteration {iteration}) in {status} mode.
        Current reads: {int(current.get('keyProgress', 0))} keystrokes,
        speed {int(current.get('speedProgress', 0))}, balance {int(current.get('handshakeProgress', 0))}.
        Changes: {diff_text}.
        Craft a unique, playful insight no longer than 120 words. Mention what the new rhythm says about the user, celebrate increases, and nudge toward smoother balance when dips appear.
        Address the user directly with "you" and keep vibe lively.
        """
    )


def fallback_message(
    current: Dict[str, Any], diff_lines: List[str], iteration: int, mode: str
) -> str:
    diff_text = diff_lines[0] if diff_lines else "steady rhythm"
    return (
        f"[{mode}] iteration {iteration}: {diff_text}. "
        f"You now sit at {int(current.get('keyProgress', 0))} strokes, "
        f"{int(current.get('speedProgress', 0))} speed points, "
        f"{int(current.get('handshakeProgress', 0))} balance points."
    )


def run_cycle(
    progress_path: Path,
    feed_path: Path,
    state_path: Path,
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
    previous_hash = state.get("last_hash")
    if current_hash == previous_hash and not dry_run:
        return False
    previous_snapshot = state.get("last_snapshot", {})
    diff_lines = describe_diff(snapshot, previous_snapshot)
    iteration = int(state.get("iteration", 0)) + 1
    prompt = build_prompt(snapshot, diff_lines, iteration, mode)
    message = fallback_message(snapshot, diff_lines, iteration, mode)
    if not dry_run:
        try:
            message = call_openai(prompt, config)
        except Exception as exc:  # pragma: no cover
            print(f"GPT bridge request failed: {exc}", file=sys.stderr)
            print("Falling back to local message.", file=sys.stderr)
    write_json(
        feed_path,
        {
            "timestamp": int(time.time()),
            "mode": mode,
            "iteration": iteration,
            "analysis_text": message,
            "diff": diff_lines,
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
            paths["feed"],
            paths["state"],
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
