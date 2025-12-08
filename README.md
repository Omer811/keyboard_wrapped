# Keyboard Wrapped (cube story branch)

This branch focuses on the cube-based story layout. Everything you see is configured from `config/app.json`, including which cubes render, which dataset is shown, and the copy that dresses the page—there is no toggle panel anymore.

## Unified config (`config/app.json`)

- `mode`: choose `real` or `sample`. The UI and AI script read this value to know what dataset to show.
- `data`: override the paths for each dataset (`real_summary`, `sample_summary`, `real_gpt`, `sample_gpt`) if you move files around.
- `gpt`: your AI settings (`api_key`, `model`, `temperature`). Leave `api_key` empty to stay in fallback mode.
- `ui_text`: customize the hero copy, control hints, footer note, and the subtitle of the AI cube.
- `visual`: tweak the number of words exposed in the pie chart, how many transitions appear, or how many entries the heatmap should show.
- `groups` and `cubes`: enable/disable cubes, assign them to groups, and set their rendering order. The UI sorts cubes by each entry’s `order` field, so you can promote the AI cube to the top or hide any story entirely from JSON.

Change this file to switch between sample/real data, adjust the story text, or bring new cubes online.

## Logger (`keyboard_logger.py`)

- **What it does:** listens for keystrokes and logs each event with `interval_ms` (gap between presses), `duration_ms` (how long the key was held), behaviors (rage, long pause), word boundaries, and per-word shapes.
- **Outputs:** `data/keystrokes.jsonl` as the raw stream and `data/summary.json` as the rolled-up stats consumed by the cubes.
- **Install:** `pip install pynput`
- **Run:** `python3 keyboard_logger.py --log data/keystrokes.jsonl --summary data/summary.json`
- **Stop:** `Ctrl+C` flushes pending keys, captures the final word, refreshes typing profiles, and writes the summary.

Once the logger runs, `data/summary.json` feeds the UI whenever `config/app.json` points at `mode: "real"`.

## Sample data

- `data/sample_summary.json` models a full year with daily activity waves, word frequencies, transitions, word shapes, and typing profiles so the cubes (and AI fallback) render a rich story immediately.
- `data/sample_keystrokes.jsonl` mirrors the logger output format for quick previews.
- `data/sample_gpt_insight.json` provides a human-friendly fallback analysis before you hook up your own API key.

## AI analysis (`gpt_insights.py`)

1. Install dependencies: `pip install openai`
2. Edit `config/app.json` and drop your OpenAI key into `gpt.api_key` (other defaults can stay).
3. Run `python3 gpt_insights.py`. The script respects the configured mode/data paths; use `--mode sample` to force the sample summary.

The script loads the chosen summary, composes a prompt that includes typing speed, per-key timing, word shapes, and adjacency, and writes the assistant’s reply to the designated GPT output file. If the OpenAI call fails or there is no key, a local AI-style fallback summary is generated so the cube always has content.

## Cube-based UI (`ui/`)

1. Serve the repository: `python3 -m http.server`
2. Open `http://localhost:8000/ui/index.html`
3. The UI reads `config/app.json` to determine the dataset, the AI output file, and which cubes to render; `order` controls the scroll order, and `ui_text`/`visual` let you tweak copy or limits.

### What you see

- **AI analysis:** arrives top of the stack. The title/description live in config, and the card summarizes persona, keyboard age, pacing, and vocabulary signals.
- **Overview pulse:** totals, letter/action balance, rage bursts, pauses, and timing averages.
- **Key flow:** bar chart for the top keys plus a 30-day pressure line.
- **Story feed:** keyboard age, AI persona card, tempo note, standout rage day, and vocabulary highlight.
- **Word choreography:** a configurable pie chart showing your favorite words.
- **Word transitions:** a dedicated cube listing the most frequent word-to-word flows.
- **Pressure profile:** your average key hold mapped to a global light/heavy presser scale with a stylized key-press visual.
- **Layout lab:** a QWERTY-inspired keyboard that keeps modifiers stationary while reflowing letters, with neighbor glow wires showing what commonly comes before/after each key.
- **Word heatmap:** vibrantly colored word bubbles whose hue mirrors frequency and diversity. Click any bubble to reveal its flow map; shapes, hover states, and callouts highlight how words move through your text.

To change which cubes appear or their order, edit the `cubes` array. All behavior (sample vs. real data, cube order, AI copy) is driven from this single JSON file.

## Running everything

- `./run.sh [--port PORT]` launches the HTTP server and opens the cube UI (default port `8000`). The UI obeys `config/app.json` for mode selection.
- `./run_gpt_ui.sh [--mode real|sample] [--port PORT]` first regenerates the AI insight for the configured summary and then starts the UI, keeping both data and dashboard synced.
