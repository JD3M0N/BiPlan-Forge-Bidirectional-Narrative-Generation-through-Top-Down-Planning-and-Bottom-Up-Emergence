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

### Install all project packages

```powershell
python -m pip install -r requirements.txt
```

Installs both the Top-Down and Bottom-Up packages in editable mode, including
their development dependencies. Editable mode means source changes are
available immediately without reinstalling the packages.


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
python -m pytest Models/Top-Down/tests
```

Runs only the Top-Down unit and integration tests. These tests use a fake
provider and do not call Gemini.

## Bottom-Up Escape Room

### Run a standard simulation

```powershell
run-escape-room
```

Runs the default escape-room map with:

- seed `0`;
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
run-escape-room --map "Models/Bottom-Up/escape-room/maps/minimal_room.json"
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
| `--seed NUMBER` | Sets the deterministic random seed. Default: `0`. |
| `--agents {2,3}` | Selects the number of characters. Default: `2`. |
| `--tick-limit NUMBER` | Sets the maximum simulation length. Default: `300`. |
| `--batch` | Runs seeds 0–29 with two and three agents. |
| `--no-llm` | Uses the local fallback narrator instead of Gemini. |
| `-h`, `--help` | Displays command help. |

### Run Bottom-Up tests

```powershell
python -m pytest Models/Bottom-Up/escape-room/tests
```

Runs map validation, movement, inventory, puzzle, cooperation,
reproducibility, narration, storage, and Top-Down adapter tests.

## Run All Tests

```powershell
python -m pytest Models/Top-Down/tests Models/Bottom-Up/escape-room/tests
```

Runs the complete automated test suite for both approaches.

Use concise output:

```powershell
python -m pytest Models/Top-Down/tests Models/Bottom-Up/escape-room/tests -q
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
