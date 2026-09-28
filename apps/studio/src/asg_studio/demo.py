"""Demo mode: show a generation's progress without calling the model or writing a run.

For presenting the interface, and for checking it by eye without spending quota. A demo job
replays the stages of a simulated run at a readable pace and finishes pointing at the latest
completed simulated run already on disk, so the reader opens something real. The header of the
page says DEMO the whole time, so nobody mistakes it for a generation.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

from asg_evaluation.artifacts import load_json_object
from asg_stagecraft.runtime.errors import RunArtifactError, RunCancelledError
from asg_stagecraft.runtime.progress import PipelineEvent, ProgressUpdate

# (percent, stage, description) as a simulated run reports them, compressed.
STEPS = (
    (0, "analysis", "Analizando la solicitud"),
    (6, "world", "Construyendo el mundo"),
    (12, "characters", "Diseñando los personajes"),
    (18, "planning", "Planificando la trama"),
    (30, "drafting", "Escribiendo el guion por escenas"),
    (50, "casting", "Preparando a los actores"),
    (58, "performance", "Representando la escena 1 de 3"),
    (68, "performance", "Representando la escena 2 de 3"),
    (78, "performance", "Representando la escena 3 de 3"),
    (86, "narration", "Narrando el capitulo 1 de 2"),
    (92, "narration", "Narrando el capitulo 2 de 2"),
    (98, "story", "Guardando la historia"),
)


def latest_simulated_run(stories_root: Path) -> Path | None:
    """Return the newest completed simulated run, or None when there is none."""
    base = Path(stories_root) / "Stagecraft"
    if not base.is_dir():
        return None
    for path in sorted((item for item in base.iterdir() if item.is_dir()), reverse=True):
        metadata = load_json_object(path / "metadata.json")
        if metadata.get("status") == "completed" and metadata.get("story_format") == "simulated":
            return path
    return None


class DemoGenerator:
    """Replay a simulated run's progress and hand back a run that already exists."""

    def __init__(self, stories_root: Path, pause: float = 0.7) -> None:
        """Remember where to find a run to point at, and how long each step lasts."""
        self.stories_root = Path(stories_root)
        self.pause = pause

    def generate(
        self,
        request,
        on_progress=None,
        on_run_created=None,
        on_event=None,
        *,
        should_cancel=None,
    ):
        """Walk through the stages, honoring a cancel between any two of them."""
        run_dir = latest_simulated_run(self.stories_root)
        if run_dir is None:
            raise RunArtifactError("No hay ninguna función simulada completa para la demostración.")
        for index, (percent, stage, description) in enumerate(STEPS):
            if should_cancel is not None and should_cancel():
                raise RunCancelledError("La demostración se canceló.")
            if on_progress is not None:
                on_progress(ProgressUpdate(percent, stage, description))
            if on_event is not None:
                on_event(PipelineEvent("agent_called", f"demo: paso {index + 1}", stage=stage))
            if index == 0 and on_run_created is not None:
                on_run_created(run_dir)
            time.sleep(self.pause)
        return SimpleNamespace(run_dir=run_dir)


def demo_factory(stories_root: Path, pause: float = 0.7):
    """Build the generator factory the job runner uses in demo mode."""

    def build(options) -> DemoGenerator:
        """Ignore the options: a demo never generates anything."""
        return DemoGenerator(stories_root, pause)

    return build
