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

The GPT script looks for an API key in `OPENAI_API_KEY` before it ever reads `config/app.json`, so you can keep your credential entirely outside the repository. Set it like `export OPENAI_API_KEY=sk-…` before running `./run_gpt_ui.sh` or `python3 gpt_insights.py`. If you need to store the key locally, keep it in a shell rc file (`~/.zshrc`, `~/.bash_profile`, etc.) and **do not commit that file** to Git—the default config now omits the key so it can stay private.

## Netlify builds

Netlify runs the command defined in `netlify.toml`, which copies `config/app.json` and the entire `data/` folder into `ui/` before publishing. The UI now tries `./config/app.json`/`./data/...` first and falls back to `../config`/`../data` so the 404 vanishes while local runs still work. During local development you can still use `./run_gpt_ui.sh --netlify` (or omit `--netlify`) to keep the config/data copy and dev server in sync, and the new status line at the top will tell you which asset path loaded or why it failed.
