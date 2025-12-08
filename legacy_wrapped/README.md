# Keyboard Wrapped

Lightweight tooling for capturing the pulse of your keyboard over a year and presenting a Spotify Wrapped–style recap.

## Logger (`keyboard_logger.py`)

- **What it does:** listens for keystrokes, categorizes each press as a letter or action, tracks words built, and spots behaviors such as rage bursts (multiple rapid presses of the same key) and long pauses (intervals > 2s).
- **Output:** raw events stream to `data/keystrokes.jsonl` and a rolling summary at `data/summary.json` that the UI consumes.
- **Install:** `pip install pynput`
- **Run:** `python3 keyboard_logger.py --log data/keystrokes.jsonl --summary data/summary.json`
- **Stop:** press `Ctrl+C` to flush the summary.

The logger now keeps track of completed words and the word-to-word transitions (Markov-style), so the UI can later visualize both favorite words and what tends to follow them.

## Sample data

- `data/sample_summary.json` covers a modeled year (daily activity, key counts, etc.) so you can test the UI without running the logger.
- `data/sample_keystrokes.jsonl` demonstrates the JSON-lines format emitted by the logger.

The sample summary now includes `word_counts` and `word_pairs` to show how the UI renders favorite words and their transitions, while the keystrokes file shows how letter/action events are buffered into words.

## UI (`ui/`)

1. Serve the repository root so the browser can `fetch` the JSON files:  
   `python3 -m http.server`
2. Open `http://localhost:8000/ui/index.html`.
3. The dashboard loads `data/summary.json` if present; otherwise it falls back to the sample, and a banner indicates that.

### Convenient launcher

Use `./run.sh [--sample] [--port PORT]` to start the server, open the browser, and optionally force the sample dataset via the `--sample` flag (omit it to use your real `data/summary.json`). The script defaults to port `8000` and will keep the HTTP server alive until you stop it (press `Ctrl+C`).

 The UI shows totals, the top dozen keys, the last 30 days of activity, favorite words, the most common word transitions, and a new story feed that paints a GPT-style persona, keyboard age, and standout rage/word days using the summary data (which now also stores `daily_rage` and `daily_word_counts`).

## Next steps

1. Run the logger while you work to build a real yearly dataset.
2. Point the UI at the generated `data/summary.json` and refresh the page.
3. Extend the logger (e.g., bucket by hour of day) or the UI (more charts or export options) if you want a deeper Wrapped experience.
