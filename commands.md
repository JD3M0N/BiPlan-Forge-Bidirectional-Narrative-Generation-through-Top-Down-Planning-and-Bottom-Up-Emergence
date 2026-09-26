# Command Reference

Run from the repository root after activating the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

| Command | Description |
| --- | --- |
| `generate-story [prompt] [--profile {essential,developed,expansive}] [--output PATH] [--model NAME] [--no-audio] [--format {narrative,script,simulated}] [--script-method {native,adapted}] [--voice {omniscient,focalized,first_person}] [--actor-memory {own,shared}]` | Generate a story; without `prompt`, asks for it interactively. `--profile` overrides the profile inferred from the prompt, and `--no-audio` skips the narration, which dominates the wall-clock time of an experiment batch. `--format script` requests a theater script instead of narrative prose, and `--script-method` picks how it is written (see [docs/guion_teatral.md](docs/guion_teatral.md)). `--format simulated` goes one step further: the characters perform that script with a memory of their own and the story is narrated from the log of what they actually did. `--voice` picks the point of view that narration is written from, and `--actor-memory shared` is its control arm, which gives every character everything public instead of only what they witnessed (see [docs/simulacion_escenica.md](docs/simulacion_escenica.md)). |
| `compare-story-runs <run>... [--output PATH]` | Compare 2+ generated runs and produce an HTML report (default `story-comparison.html`). |
| `recover-story-runs [--stories PATH] [--close] [--discard] [--all]` | Close or discard the runs a killed process left stranded in `running`, which `StoryRun` refuses to open. Without a flag it only lists and classifies them: a run with `story.md` and a supported pipeline version can be closed as `completed`, the rest can only be discarded as `failed`. No artifact is ever deleted. Defaults to `Stories/Stagecraft`; pass `--stories Stories/Top-Down` for runs generated before 7.0. |
| `run-escape-room [--map PATH] [--seed N] [--agents {2,3}] [--tick-limit N] [--batch] [--no-llm]` | Run the Bottom-Up escape-room simulation. `--batch` runs the 60-simulation experiment matrix; `--no-llm` uses the deterministic fallback narrator instead of Gemini. |
| `report-evaluations [--stories PATH] [--csv PATH] [--group {story,profile,version,version-profile,approach,all}]` | Summarize the stored human evaluations (mean, standard deviation and variance per metric) and optionally export one CSV row per evaluation. |
| `report-story-craft [--stories PATH] [--csv PATH] [--group {story,profile,version,version-profile,approach,status,all}] [--min-version V] [--include-unversioned] [--approach NAME] [--all-status] [--format {narrative,script,simulated,prose,all}]` | Measure the prose craft of every stored story —dialogue proportion, words per sentence and words per paragraph— recomputed from `story.md`, and group it with median and range. `--min-version` defaults to `6`, so unversioned runs stay out unless `--include-unversioned` asks for them; unfinished runs reach the CSV but not the summary unless `--all-status` is given. `--format` defaults to `narrative` because `craft_metrics` reads dialogue by quote marks or a leading dash and would measure almost none in a theater script; `prose` selects the two formats that do deliver prose, narrative and simulated, which is the comparison the hybrid pipeline exists to make. |
| `report-simulations [--stories PATH] [--csv PATH] [--group {story,voice,memory,profile,version,voice-memory,all}] [--all-status]` | Summarize every stored performance: beats reached against beats forced, turns per beat, repetition, how far the improvised lines drifted from the script (`script_echo`), knowledge-boundary leaks and cost, grouped by the axes the thesis turns. |
| `asg-console` | Open the unified interactive console (Stagecraft, Bottom-Up, evaluation). |
| `asg-telegram` | Launch the Telegram bot in a separate console. |
| `asg-telegram-run` | Run the Telegram bot in the current console. |
