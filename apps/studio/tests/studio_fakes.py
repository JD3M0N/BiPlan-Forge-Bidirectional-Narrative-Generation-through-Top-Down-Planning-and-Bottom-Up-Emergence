"""Stored runs and a fake generator for the StageCraft tests: no Gemini, nothing under Stories/."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

from asg_stagecraft import GenerationOptions
from asg_stagecraft.formats import ScriptMethod
from asg_stagecraft.runtime.errors import ConfigurationError, RunCancelledError
from asg_stagecraft.runtime.progress import PipelineEvent, ProgressUpdate
from asg_stagecraft.schemas import (
    ActScript,
    PlayCastMember,
    PlayScript,
    SceneCastMember,
    ScriptLine,
    ScriptScene,
)
from asg_stagecraft.stage.schemas import (
    BeatRecord,
    PerformanceArtifact,
    PerformanceSettings,
    ScenePerformance,
    StageTurn,
)


def write(path: Path, document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = document if isinstance(document, str) else json.dumps(document, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")


def simulated_run(
    stories: Path, name: str, *, memory: str = "own", prompt: str = "Una obra"
) -> Path:
    run = stories / "Stagecraft" / name
    options = GenerationOptions(story_format="simulated", actor_memory=memory)
    write(run / "generation_options.json", options.model_dump(mode="json"))
    write(
        run / "metadata.json",
        {
            "status": "completed",
            "pipeline_version": "7.3",
            "model": "fake-model",
            "created_at": f"2026-09-27T10:00:0{len(name) % 10}Z",
            "story_format": "simulated",
            "narrative_voice": "omniscient",
            "actor_memory": memory,
            "narrative_profile": "essential",
            "warnings": ["[NARRATOR_ABSENT] Capitulo 2: ..."],
        },
    )
    write(run / "request.json", {"original_prompt": prompt, "title": "The Lighthouse"})
    write(run / "story.md", "# El faro\n\n## Uno\n\nAna subió.\n\n—¿Quién va? —dijo.\n")
    write(run / "story_metrics.json", {"words": 7, "chapters": 1})
    write(run / "simulation_metrics.json", {"beats_forced": 0, "repetition_ratio": 0.05})
    write(run / "characters.json", {"characters": [{"id": "ana", "name": "Ana"}]})
    turns = [
        StageTurn(
            id="c1-scene-1-t001",
            scene_id="c1-scene-1",
            number=1,
            actor_id="ana",
            beat_index=0,
            witnesses=["ana", "luis"],
            speech="Aqui estoy.",
            thought="Nadie me vio.",
            tactic="confront",
        ),
        StageTurn(
            id="c1-scene-1-t002",
            scene_id="c1-scene-1",
            number=2,
            actor_id="luis",
            beat_index=0,
            witnesses=["luis"],
            speech="Nadie mas.",
            visibility="whisper",
            tactic="lie",
        ),
    ]
    performance = PerformanceArtifact(
        language="Spanish",
        settings=PerformanceSettings(
            actor_memory=memory,
            turns_per_beat=8,
            check_every=3,
            retrieved_records=6,
            recency_decay=0.25,
            repetition_threshold=0.75,
        ),
        scenes=[
            ScenePerformance(
                scene_id="c1-scene-1",
                number=1,
                chapter_id="c1",
                turns=turns,
                beats=[BeatRecord(event_id="e1", index=0, achieved=True)],
            )
        ],
    )
    write(run / "performance.json", performance.model_dump_json())
    play = PlayScript(
        title="El faro",
        language="Spanish",
        script_method=ScriptMethod.NATIVE,
        cast_heading="Personajes",
        act_label="Acto",
        scene_label="Escena",
        cast=[
            PlayCastMember(character_id="ana", name="Ana"),
            PlayCastMember(character_id="luis", name="Luis"),
        ],
        acts=[
            ActScript(
                chapter_id="c1",
                number=1,
                title="Uno",
                scenes=[
                    ScriptScene(
                        id="c1-scene-1",
                        number=1,
                        event_ids=["e1"],
                        setting="El faro, de noche.",
                        cast=[
                            SceneCastMember(character_id="ana", objective="saber"),
                            SceneCastMember(character_id="luis", objective="callar"),
                        ],
                        lines=[ScriptLine(kind="direction", text="Oscuro.")],
                    )
                ],
            )
        ],
    )
    write(run / "script.json", play.model_dump_json())
    return run


def settings_loader(*, key: str = ""):
    """Build a settings loader that reports a key or its absence, like load_settings."""

    def load(start=None, *, require_api_key: bool = True):
        if require_api_key and not key:
            raise ConfigurationError("Falta GEMINI_API_KEY. Añádela al archivo .env de la raíz.")
        return SimpleNamespace(api_key=key, model="fake-model", turns_per_beat=6)

    return load


class FakeGenerator:
    """Report a little progress, honor a cancel, and hand back a run folder."""

    def __init__(self, stories: Path, *, gate: threading.Event | None = None, fail=None):
        self.stories = stories
        self.gate = gate
        self.fail = fail
        self.requests = []

    def generate(
        self, request, on_progress=None, on_run_created=None, on_event=None, *, should_cancel=None
    ):
        self.requests.append(request)
        run_dir = self.stories / "Stagecraft" / f"run-{len(self.requests)}"
        run_dir.mkdir(parents=True, exist_ok=True)
        on_run_created(run_dir)
        on_progress(ProgressUpdate(10, "analysis", "Analizando la solicitud"))
        on_event(PipelineEvent("agent_called", "se llamo al agente analyst", stage="analysis"))
        on_event(
            PipelineEvent(
                "artifact_updated", "turno", stage="performance", artifact="stage/s/turns.jsonl"
            )
        )
        on_progress(ProgressUpdate(52, "rate_limit", "Esperando cuota: 3s"))
        if self.gate is not None:
            self.gate.wait(5)
        if should_cancel and should_cancel():
            raise RunCancelledError("La generación se canceló a petición de quien la lanzó.")
        if self.fail is not None:
            raise self.fail
        return SimpleNamespace(run_dir=run_dir)
