"""The run library: list stored runs, open one, and rebuild the form that would repeat it.

Everything here reads artifacts from disk tolerantly, the way the evaluation reports do: a run
from any version opens, and what it never recorded is shown as absent. Nothing here writes or
deletes anything under Stories/, which is research data.

A run is addressed by its collection (the folder under Stories/) and its folder name. Both are
checked against the folders that exist, so a request can never reach outside Stories/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from asg_evaluation.artifacts import load_json_object, text_field
from asg_evaluation.pairing import AXES, METRICS, pair_runs, read_run_config, run_measurements
from asg_stagecraft import GenerationOptions, StoryBrief
from asg_stagecraft.formats import NarrativeVoice
from asg_stagecraft.schemas import PlayScript
from asg_stagecraft.stage.names import resolve_character
from asg_stagecraft.stage.narration import scene_presence
from asg_stagecraft.stage.schemas import PerformanceArtifact
from asg_stagecraft.stage.voices import VOICES, visible_turns
from pydantic import ValidationError

COLLECTIONS = ("Stagecraft", "Top-Down")
_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RunNotFound(LookupError):
    """Raised when a collection or run folder does not exist or is not addressable."""


class Library:
    """Read the runs stored under one Stories/ folder."""

    def __init__(self, stories_root: Path) -> None:
        """Remember where the collections live."""
        self.stories_root = Path(stories_root)

    # -- addressing ----------------------------------------------------------------------

    def run_dir(self, collection: str, run_id: str) -> Path:
        """Resolve one run folder, refusing anything that is not a run inside a collection."""
        if collection not in COLLECTIONS or not _RUN_NAME.match(run_id or ""):
            raise RunNotFound(f"{collection}/{run_id}")
        base = (self.stories_root / collection).resolve()
        path = (base / run_id).resolve()
        if path.parent != base or not path.is_dir():
            raise RunNotFound(f"{collection}/{run_id}")
        return path

    def resolve(self, reference: str) -> Path:
        """Resolve a "collection/run" reference, as the comparison view sends them."""
        collection, _, run_id = reference.partition("/")
        return self.run_dir(collection, run_id)

    # -- listing -------------------------------------------------------------------------

    def list_runs(self, collection: str | None = None) -> list[dict[str, Any]]:
        """Describe every run of one collection, or of all of them, newest first."""
        cards = []
        for name in COLLECTIONS if collection is None else (collection,):
            base = self.stories_root / name
            if name not in COLLECTIONS or not base.is_dir():
                continue
            for path in base.iterdir():
                if path.is_dir() and _RUN_NAME.match(path.name):
                    cards.append(self._card(name, path))
        return sorted(cards, key=lambda card: card["created_at"] or card["run_id"], reverse=True)

    def _card(self, collection: str, path: Path) -> dict[str, Any]:
        """Describe one run in a line of the library."""
        metadata = load_json_object(path / "metadata.json")
        config = read_run_config(path)
        story_metrics = load_json_object(path / "story_metrics.json")
        return {
            "collection": collection,
            "run_id": path.name,
            "title": config.title,
            "status": text_field(metadata, "status") or "desconocido",
            "created_at": text_field(metadata, "created_at"),
            "pipeline_version": config.pipeline_version,
            "model": config.axes.get("model"),
            "story_format": config.axes.get("story_format"),
            "script_method": config.axes.get("script_method"),
            "narrative_voice": config.axes.get("narrative_voice"),
            "actor_memory": config.axes.get("actor_memory"),
            "narrative_profile": config.axes.get("narrative_profile"),
            "warnings": len(metadata.get("warnings") or []),
            "words": story_metrics.get("words"),
            "has_story": (path / "story.md").is_file(),
            "has_audio": (path / "story.mp3").is_file(),
            "has_performance": (path / "performance.json").is_file(),
        }

    # -- one run -------------------------------------------------------------------------

    def detail(self, collection: str, run_id: str) -> dict[str, Any]:
        """Everything the reader shows about one run."""
        path = self.run_dir(collection, run_id)
        metadata = load_json_object(path / "metadata.json")
        config = read_run_config(path)
        characters = load_json_object(path / "characters.json").get("characters") or []
        narration = load_json_object(path / "narration.json")
        measured = run_measurements(path)
        return {
            **self._card(collection, path),
            "error": text_field(metadata, "error"),
            "error_code": text_field(metadata, "error_code"),
            "warnings_list": list(metadata.get("warnings") or []),
            "completed_stages": list(metadata.get("completed_stages") or []),
            "axes": config.axes,
            "sources": config.sources,
            "narrated_by": _cast_name(characters, config.narrated_by),
            "narration": {
                "voice": narration.get("narrative_voice"),
                "source": narration.get("narrator_source"),
                "chapters": narration.get("chapters") or [],
            },
            "cast": [
                {"id": item.get("id"), "name": item.get("name"), "role": item.get("role")}
                for item in characters
                if isinstance(item, dict)
            ],
            "brief": load_json_object(path / "brief.json") or None,
            "story": parse_story(_read(path / "story.md")),
            "metrics": [
                {
                    "key": metric.key,
                    "label": metric.label,
                    "group": metric.group,
                    "value": measured[metric.key],
                }
                for metric in METRICS
                if measured[metric.key] is not None
            ],
        }

    def audio_path(self, collection: str, run_id: str) -> Path:
        """Return the run's story.mp3, or raise when it has none."""
        path = self.run_dir(collection, run_id) / "story.mp3"
        if not path.is_file():
            raise RunNotFound(f"{collection}/{run_id}/story.mp3")
        return path

    def performance(
        self, collection: str, run_id: str, *, voice: str = "", narrator: str = ""
    ) -> dict[str, Any]:
        """Return the performed log, marking what a given point of view could see of it."""
        path = self.run_dir(collection, run_id)
        try:
            performance = PerformanceArtifact.model_validate(
                json.loads((path / "performance.json").read_text(encoding="utf-8"))
            )
            play = PlayScript.model_validate(
                json.loads((path / "script.json").read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, ValidationError) as exc:
            raise RunNotFound(f"{collection}/{run_id}/performance.json") from exc
        names = {member.character_id: member.name for member in play.cast}
        settings = {scene.id: scene.setting for act in play.acts for scene in act.scenes}
        presence = scene_presence(play)
        chosen = _voice(voice)
        narrator_id = resolve_character(narrator, names) if narrator else ""
        if chosen is not None and VOICES[chosen].needs_narrator and not narrator_id:
            narrator_id = next(iter(names), "")
        scenes = []
        for scene in performance.scenes:
            seen = (
                {
                    turn.id: turn
                    for turn in visible_turns(
                        chosen, scene, narrator=narrator_id, present=presence.get(scene.scene_id)
                    )
                }
                if chosen is not None
                else None
            )
            scenes.append(
                {
                    "scene_id": scene.scene_id,
                    "chapter_id": scene.chapter_id,
                    "setting": settings.get(scene.scene_id, ""),
                    "turns": [_turn_view(turn, names, seen) for turn in scene.turns],
                }
            )
        return {
            "voice": chosen.value if chosen else "",
            "narrator": narrator_id,
            "cast": [{"id": key, "name": value} for key, value in names.items()],
            "scenes": scenes,
        }

    def replay(self, collection: str, run_id: str) -> dict[str, Any]:
        """Rebuild the Create form that would repeat this run, from its own records."""
        path = self.run_dir(collection, run_id)
        options = _recorded_options(path)
        brief = load_json_object(path / "brief.json")
        if brief:
            try:
                return {
                    "mode": "brief",
                    "brief": StoryBrief.model_validate(brief).model_dump(mode="json"),
                    "prompt": "",
                    "options": options,
                }
            except ValidationError:
                pass
        request = load_json_object(path / "request.json")
        prompt = text_field(request, "original_prompt") or text_field(
            load_json_object(path / "submitted_request.json"), "prompt"
        )
        return {"mode": "prompt", "brief": None, "prompt": prompt or "", "options": options}

    def compare(self, references: list[str]) -> dict[str, Any]:
        """Put two to four runs side by side, axis by axis and figure by figure."""
        paths = [self.resolve(reference) for reference in references]
        pairing = pair_runs(paths)
        metric_rows = [
            {
                "key": metric.key,
                "label": metric.label,
                "group": metric.group,
                "values": pairing.metrics[metric.key],
            }
            for metric in METRICS
            if any(value is not None for value in pairing.metrics[metric.key])
        ]
        return {
            "runs": [
                {
                    "reference": reference,
                    "run_id": config.run_id,
                    "title": config.title,
                    "status": config.status,
                    "pipeline_version": config.pipeline_version,
                    "narrated_by": config.narrated_by,
                    "axes": config.axes,
                }
                for reference, config in zip(references, pairing.configs, strict=True)
            ],
            "axes": [
                {"key": axis.key, "label": axis.label, "formats": sorted(axis.formats or [])}
                for axis in AXES
            ],
            "differing_axes": pairing.differing_axes,
            "unknown_axes": pairing.unknown_axes,
            "clean": pairing.clean,
            "warnings": pairing.warnings,
            "metrics": metric_rows,
        }


def parse_story(markdown: str) -> dict[str, Any]:
    """Split a story into its title and chapters of paragraphs, for rendering as plain text."""
    title = ""
    chapters: list[dict[str, Any]] = []
    paragraph: list[str] = []

    def close_paragraph() -> None:
        """Move the lines gathered so far into the current chapter as one paragraph."""
        if paragraph:
            if not chapters:
                chapters.append({"title": "", "paragraphs": []})
            chapters[-1]["paragraphs"].append(" ".join(paragraph).strip())
            paragraph.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            close_paragraph()
            chapters.append({"title": line[3:].strip(), "paragraphs": []})
        elif line.startswith("# ") and not title:
            close_paragraph()
            title = line[2:].strip()
        elif not line:
            close_paragraph()
        else:
            paragraph.append(line.replace("**", "").replace("__", ""))
    close_paragraph()
    return {"title": title, "chapters": chapters}


def _read(path: Path) -> str:
    """Read a text artifact, or nothing when it is missing or unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _cast_name(characters: list, character_id: str) -> str:
    """Return a cast member's name by id, or the id when the cast does not list them."""
    for item in characters:
        if isinstance(item, dict) and item.get("id") == character_id:
            return str(item.get("name") or character_id)
    return character_id


def _voice(value: str) -> NarrativeVoice | None:
    """Parse a voice name, or None to show the log without any point of view."""
    try:
        return NarrativeVoice(value) if value else None
    except ValueError:
        return None


def _turn_view(turn, names: dict[str, str], seen: dict | None) -> dict[str, Any]:
    """Describe one turn, and what the chosen point of view kept of it."""
    kept = seen.get(turn.id) if seen is not None else turn
    return {
        "id": turn.id,
        "kind": turn.kind,
        "actor_id": turn.actor_id,
        "name": names.get(turn.actor_id, turn.actor_id),
        "speech": turn.speech,
        "action": turn.action,
        "thought": turn.thought,
        "visibility": turn.visibility,
        "addressed_to": [names.get(item, item) for item in turn.addressed_to],
        "visible": kept is not None,
        "thought_visible": bool(kept is not None and kept.thought),
    }


def _recorded_options(path: Path) -> dict[str, Any]:
    """Read a run's options, rebuilding them from older artifacts when it has no record."""
    recorded = load_json_object(path / "generation_options.json")
    if recorded:
        try:
            return GenerationOptions.model_validate(recorded).model_dump(mode="json")
        except ValidationError:
            pass
    axes = read_run_config(path).axes
    values = {
        key: axes[key]
        for key in GenerationOptions.model_fields
        if key in axes and axes[key] is not None
    }
    try:
        return GenerationOptions.model_validate(values).model_dump(mode="json")
    except ValidationError:
        return GenerationOptions().model_dump(mode="json")
