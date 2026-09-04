# Command Reference

Run these commands from the repository root:

```text
E:\University\thesis
```
## Environment Setup

### Create the virtual environment

```powershell
python -m venv .venv
```

### Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

```powershell
.\venv.ps1
```

### Install all project packages and development tools

```powershell
python -m pip install -r requirements-dev.txt
```

Installs the applications and packages in editable mode plus pytest and Ruff.
Editable mode means source changes are
available immediately without reinstalling the packages.

The installation exposes these commands:

| Command | Purpose |
| --- | --- |
| `asg-console` | Open the unified interactive console. |
| `generate-story` | Run the Top-Down story generator directly. |
| `compare-story-runs` | Compare two or more generated story runs. |
| `run-escape-room` | Run the Bottom-Up escape-room simulation directly. |
| `asg-telegram` | Launch the Telegram bot in a separate Windows console. |
| `asg-telegram-run` | Run the Telegram bot in the current console. |


## Top-Down

### Generate a story

```powershell
generate-story
```


The generated artifacts and final story are saved under:

```text
Stories/Top-Down/<timestamp>-<story-title>/
```

### Run Top-Down tests

```powershell
python -m pytest packages/top_down/tests
```

Runs only the Top-Down unit and integration tests. These tests use a fake
provider and do not call Gemini.

## Unified Console

### Open the interactive model navigator

```powershell
asg-console
```

Opens the main menu:

```text
1. Top-Down
2. Bottom-Up
3. Evaluate story
0. Exit
```

The Top-Down menu runs `Generate story`. The Bottom-Up menu provides a normal
escape-room run, the 60-run batch experiment, and the live visual mode. The
existing `generate-story` and `run-escape-room` commands remain available for
scripts and direct execution.

`Evaluate story` searches both story families, asks for an evaluator user and
the six scores from 1 to 10, then appends the result to `evaluation.json`.

### Use Escape Room Visual

Choose `Bottom-Up`, then `Escape Room Visual`. The console asks for the map,
agent count, optional seed, tick limit, Gemini preference, and display
interval. Press Enter at a prompt to accept its displayed default.

The live controls are:

| Key | Action |
| --- | --- |
| `Space` | Pause or resume automatic playback. |
| `N` | Execute one tick while paused. |
| `+` | Reduce the delay and speed up playback. |
| `-` | Increase the delay and slow down playback. |
| `V` | Cycle through the complete world and each agent's partial view. |
| `Q` | Stop and discard the visual run without creating artifacts. |

The default interval is 1.5 seconds and can be adjusted between 0.1 and 5
seconds. A completed visual run saves the same artifacts as
`run-escape-room`, including the final story.

### Run unified-console tests

```powershell
python -m pytest apps/console/tests
```

Tests menu navigation, input validation, rendering, fog of war, keyboard
controls, cancellation, and completed-run persistence without real-time waits
or Gemini calls.

## Bottom-Up Escape Room

### Run a standard simulation

```powershell
run-escape-room
```

Runs the default escape-room map with:

- a newly generated random seed;
- `2` agents;
- a limit of `300` ticks;
- Gemini narration when an API key is available.

The complete run is saved under:

```text
Stories/Bottom-Up/Escape-Room/<timestamp>-<room-name>/
```

### Run with explicit settings

```powershell
run-escape-room --seed 7 --agents 3 --tick-limit 300
```

Runs a reproducible simulation using seed `7`, three agents, and a maximum of
300 ticks.

### Select a map

```powershell
run-escape-room --map "packages/escape_room/maps/minimal_room.json"
```

Loads the specified room instead of the default map. The chosen map must
define at least as many agents as requested with `--agents`.

### Generate the fallback story without Gemini

```powershell
run-escape-room --no-llm
```

Skips the Gemini request and creates the deterministic template-based story.
Simulation traces, events, results, and metrics are still generated normally.

### Run the complete experiment matrix

```powershell
run-escape-room --batch --tick-limit 300
```

Runs seeds `0` through `29` with both two-agent and three-agent configurations,
for a total of 60 simulations. It saves:

```text
Stories/Bottom-Up/Escape-Room/experiments/<timestamp>/runs.csv
Stories/Bottom-Up/Escape-Room/experiments/<timestamp>/summary.csv
```

`runs.csv` contains one row per simulation. `summary.csv` reports aggregate
escape rates and average successful completion times.

### Display Bottom-Up CLI help

```powershell
run-escape-room --help
```

Displays all supported command-line options:

| Option | Description |
| --- | --- |
| `--map PATH` | Selects a room JSON file. |
| `--seed NUMBER` | Sets a reproducible seed. When omitted, a random seed is generated and saved. |
| `--agents {2,3}` | Selects the number of characters. Default: `2`. |
| `--tick-limit NUMBER` | Sets the maximum simulation length. Default: `300`. |
| `--batch` | Runs seeds 0–29 with two and three agents. |
| `--no-llm` | Uses the local fallback narrator instead of Gemini. |
| `-h`, `--help` | Displays command help. |

### Run Bottom-Up tests

```powershell
python -m pytest packages/escape_room/tests
```

Runs map validation, movement, inventory, puzzle, cooperation,
reproducibility, narration, storage, and action-resolution tests.

## Run All Tests

```powershell
python -m pytest -q -p no:cacheprovider
```

Runs the complete automated test suite for evaluation and both approaches.

Use concise output:

```powershell
python -m pytest packages/top_down/tests packages/escape_room/tests -q -p no:cacheprovider
```

The `-q` flag reduces pytest output while still showing failures and the final
test summary.

## Useful Git Commands

### Inspect changed files

```powershell
git status --short
```

Shows modified and untracked files in a compact format.

### Inspect the current patch

```powershell
git diff
```

Displays unstaged changes to tracked files.

### Check for whitespace errors

```powershell
git diff --check
```

Detects trailing whitespace and other patch-formatting problems before a
commit.
