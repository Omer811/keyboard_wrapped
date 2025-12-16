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
from scripts.logger_health import append_debug

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from gpt_insights import call_openai, resolve_paths as gpt_insight_paths
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


def _load_cached_insight(config: Dict[str, Any], mode: str, root: Path) -> Optional[str]:
    try:
        insight_paths = gpt_insight_paths(config, mode)
        insight_file = root / insight_paths["output"]
        if not insight_file.exists():
            return None
        data = load_json(insight_file)
        return (
            data.get("analysis_text")
            or data.get("analysis")
            or (data.get("structured") or {}).get("analysis_text")
        )
    except Exception:
        return None


def build_prompt(
    current: Dict[str, Any],
    diff_lines: List[str],
    iteration: int,
    mode: str,
    previous: Dict[str, Any],
) -> str:
    status = "live" if mode == "real" else "sample"
    diff_text = "; ".join(diff_lines) or "steady rhythm"
    prev_summary = (
        f"Previous keystrokes {int(previous.get('keyProgress', 0))}, speed {int(previous.get('speedProgress', 0))}, balance {int(previous.get('handshakeProgress', 0))}."
        if previous
        else "No prior snapshot."
    )
    key_goal = max(0, 5000 - current.get("keyProgress", 0))
    balance_goal = max(0, 80 - current.get("handshakeProgress", 0))
    speed_goal = max(0, 120 - current.get("speedProgress", 0))
    return textwrap.dedent(
        f"""\
        You are KeyboardAI. The widget just refreshed (iteration {iteration}) in {status} mode.
        Current reads: {int(current.get('keyProgress', 0))} keystrokes,
        speed {int(current.get('speedProgress', 0))}, balance {int(current.get('handshakeProgress', 0))}.
        Changes: {diff_text}.
        Previous snapshot: {prev_summary}
        Mission: Close the rings by capturing {key_goal} more keystrokes, boosting speed toward {speed_goal} rhythm points, raising balance up to {balance_goal}, and nudging accuracy every time you mistype a favorite word.
        Craft a unique, playful insight no longer than 120 words. Mention what the new rhythm says about the user, celebrate increases, and nudge toward smoother balance when dips appear.
        Address the user directly with "you" and keep vibe lively.
        Provide one concrete action the user can take after reading this insight. Do not repeat the same status or rehash the previous prompt—transform it into a motivating pep talk that keeps the focus on the ring goals.
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
    debug_path: Path,
    config: Dict[str, Any],
    mode: str,
    dry_run: bool,
    root: Path,
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
    prompt = build_prompt(snapshot, diff_lines, iteration, mode, previous_snapshot)
    cached_insight = _load_cached_insight(config, mode, root)
    if cached_insight:
        append_debug(f"Reusing cached insight for mode {mode}", debug_path)
    message = cached_insight or fallback_message(snapshot, diff_lines, iteration, mode)
    if not dry_run and not cached_insight:
        append_debug(
            f"GPT prompt (mode {mode}, iteration {iteration}): {prompt[:400].replace(os.linesep, ' ')}",
            debug_path,
        )
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
            root,
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
