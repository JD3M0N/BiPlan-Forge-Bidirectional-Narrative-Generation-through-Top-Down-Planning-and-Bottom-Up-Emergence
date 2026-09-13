# Command Reference

Run from the repository root after activating the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

| Command | Description |
| --- | --- |
| `generate-story [prompt] [--profile {essential,developed,expansive}] [--output PATH] [--model NAME] [--no-audio]` | Generate a Top-Down story; without `prompt`, asks for it interactively. `--profile` overrides the profile inferred from the prompt, and `--no-audio` skips the narration, which dominates the wall-clock time of an experiment batch. |
| `compare-story-runs <run>... [--output PATH]` | Compare 2+ generated runs and produce an HTML report (default `story-comparison.html`). |
| `run-escape-room [--map PATH] [--seed N] [--agents {2,3}] [--tick-limit N] [--batch] [--no-llm]` | Run the Bottom-Up escape-room simulation. `--batch` runs the 60-simulation experiment matrix; `--no-llm` uses the deterministic fallback narrator instead of Gemini. |
| `report-evaluations [--stories PATH] [--csv PATH] [--group {story,profile,version,version-profile,approach,all}]` | Summarize the stored human evaluations (mean, standard deviation and variance per metric) and optionally export one CSV row per evaluation. |
| `asg-console` | Open the unified interactive console (Top-Down, Bottom-Up, evaluation). |
| `asg-telegram` | Launch the Telegram bot in a separate console. |
| `asg-telegram-run` | Run the Telegram bot in the current console. |
