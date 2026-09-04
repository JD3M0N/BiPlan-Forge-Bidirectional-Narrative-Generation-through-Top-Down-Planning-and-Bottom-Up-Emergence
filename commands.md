# Command Reference

Run from the repository root after activating the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

| Command | Description |
| --- | --- |
| `generate-story [prompt]` | Generate a Top-Down story; without `prompt`, asks for it interactively. |
| `compare-story-runs <run>... [--output PATH]` | Compare 2+ generated runs and produce an HTML report (default `story-comparison.html`). |
| `run-escape-room [--map PATH] [--seed N] [--agents {2,3}] [--tick-limit N] [--batch] [--no-llm]` | Run the Bottom-Up escape-room simulation. `--batch` runs the 60-simulation experiment matrix; `--no-llm` uses the deterministic fallback narrator instead of Gemini. |
| `asg-console` | Open the unified interactive console (Top-Down, Bottom-Up, evaluation). |
| `asg-telegram` | Launch the Telegram bot in a separate console. |
| `asg-telegram-run` | Run the Telegram bot in the current console. |
