# Keyboard Wrapped (cube story branch)

Keyboard Wrapped is a professional mockup for presenting a full-year, AI-enhanced keyboard story. The UI layers cubes that summarize performance, wordplay, and rhythm; the prompt and the resulting GPT insight are the only moving parts, so the experience stays polished and focused.

## Visual story

- **Cube Stories:** a calm, premium hero invites you to scroll vertically through curated sections.
- **Story Feed:** GPT-powered insight cards that spell out your keyboard age, persona, tempo, standout days, and vocabulary story.
- **Overview Pulse:** totals and the live balance between letters, actions, and pauses.
- **Key Flow:** a bar chart of your top keys matched with a 30-day pressure line.
- **Word Choreography:** a doughnut showing your favorite words with cinematic gradients.
- **Word Transitions:** a list of the most frequent word hops.
- **Pressure Profile:** your average hold mapped to a light/heavy slider with a subtle percentage indicator.
- **Layout Lab:** a keyboard grid that keeps modifiers in place while safely reflowing letters and highlighting the neighbors you visit most.
- **Word Heatmap:** luminous bubbles whose colors map frequency and diversity; clicking one draws its flow so you can read the cadence.

Every cube is controlled through `config/app.json`, so you can rearrange them, flip between datasets, and refresh the GPT narration without touching the UI code.

## OpenAI integration

The GPT script looks for an API key in `OPENAI_API_KEY` before it ever reads `config/app.json`, so you can keep your credential entirely outside the repository. Set it like `export OPENAI_API_KEY=sk-…` before running `./run_gpt_ui.sh` or `python3 gpt_insights.py`. To avoid typing that every time, copy `config/gpt_key.example.json` to `config/gpt_key.json`, put the key under `"api_key"`, and the menu-bar launcher will automatically load it into the environment before it starts the bridge. Don’t commit `config/gpt_key.json`—it’s ignored for your privacy.

## Netlify builds

Netlify runs the command defined in `netlify.toml`, which copies `config/app.json` and the entire `data/` folder into `ui/` before publishing. The UI now tries `./config/app.json`/`./data/...` first and falls back to `../config`/`../data` so the 404 vanishes while local runs still work. During local development you can still use `./run_gpt_ui.sh --netlify` (or omit `--netlify`) to keep the config/data copy and dev server in sync, and the new status line at the top will tell you which asset path loaded or why it failed.

## Menu-bar companion

The `mac-widget` executable is a tiny Swift status-bar helper that reads the same `data/summary.json` (or `data/sample_summary.json` when you pass `scripts/run_menu_app.sh --sample`) so you get synchronized rings inside macOS’ menu bar. Build it with `scripts/build_menu_app.sh`, then launch with `scripts/run_menu_app.sh` (pass `--sample` to switch modes). The launcher now ships three helpful flags:

- `--log` enables detailed keystroke logging so you can trace every capture inside `data/widget_debug.log`.
- `--gpt-loop` keeps the GPT bridge running in the background if you want a steady narration in addition to the on-open refresh.
- `--monitor` flips the widget into a monitoring overlay: it exposes the raw `widget_debug.log` tail, the GPT iteration/connectivity chatter, and the handshake diagnostics. Without `--monitor` the UI stays streamlined—no debug cards, no GPT iteration noise—but you still get the same enlarged AI insight card and the new keyboard balance hint so the counters feel more polished.

The script now also cleans up the logger/GPT helper PIDs when you close the menu app, so kill switches and terminal terminations don’t leave background listeners chewing on your keys.

The Swift app watches the shared JSON files, recomputes the keystroke/speed/handshake rings, writes `data/widget_progress.json`, and keeps the experience aligned with the dashboard without double-monitoring the keyboard. The widget now publishes a handshake hint under the rings (and a colorful AI insight card) so you can see when your keyboard balance actually phases in—type widely separated letters to watch the handshake score rise, and switch to `--monitor` if you need to inspect the raw log tail and GPT loop chatter.

### Typing accuracy ring

Typing accuracy is now a fourth ring within the widget. Every correctly spelled word adds points, while misspelled words subtract points (configurable via the `word_accuracy` block in `config/app.json`). The Python logger checks each finished word using `scripts/word_checker.py` (which prefers `wordfreq` if installed, but falls back to a builtin list of common English words) and records the score in `summary["word_accuracy"]`. The widget reads that score and displays the ring along with your target, so you can literally watch the accuracy bar climb as you nail more words.

To improve the dictionary, install `wordfreq` via `pip install wordfreq`. Otherwise the bundled fallback already recognizes a curated list of common English terms and keeps the scoring flowing.

The accuracy score only counts words when you hit space, so punctuation or long pauses won't split a word. That matches the summary's word boundaries, preventing stray entries like `myname` when you pause mid-word.

### Debug helpers

When you need to exercise the flow without actually typing, `scripts/mock_keystrokes.py` injects synthetic events (it touches `data/summary.json`, `data/keystrokes.jsonl`, and `data/widget_debug.log`) so you can confirm the widget rings move and the GPT bridge has new data. Run something like:

```
python3 scripts/mock_keystrokes.py --sequence craft --interval 140 --duration 55
tail -f data/widget_debug.log   # see your injection logged
tail -f data/widget_progress.json  # confirm the Swift monitor rewrote the snapshot
```

The widget now writes detailed summary stats back to `data/widget_debug.log` every time it recalculates the rings, so you can watch `total_events`, `avg_interval`, the handshake score, and the number of key-pair neighbors to make sure the pipeline truly reacts to the latest keystrokes.

For developers, `swift test` inside `mac-widget` now runs `SummaryStatsTests`, which exercise the same math the widget uses to compute speed, handshake, and key-pair counts so you can trust that `data/widget_progress.json` reflects the transformed summary data.

## Layout cube flags

Use `visual.layout_show_prev_keys` and `visual.layout_show_next_keys` in `config/app.json` to toggle whether the Layout Lab cube highlights the preceding or following key sequences; both default to `true`, letting you focus on the direction that matters most.
# Demo helper
To reset the daily activity/rage/word counters before showing off the UI, run:

```bash
python3 scripts/reset_summary.py --summary data/summary.json
```
