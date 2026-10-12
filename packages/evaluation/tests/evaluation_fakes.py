"""Synthetic runs and a deterministic extraction provider shared by evaluation tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text
from asg_evaluation.features import (
    FeatureFinding,
    Findings,
    Occurrence,
    Presence,
    Quote,
    Scene,
    Segmentation,
)


class SyntheticProvider:
    """Return deterministic evidence for artificial demo texts, without a network client."""

    def __init__(self) -> None:
        """Count fake calls so tests can verify checkpoint and cache behavior."""
        self.calls = 0

    def generate_structured(self, *, system_instruction, prompt, schema, profile):
        """Extract the deliberately simple demo facts into the production response schemas."""
        self.calls += 1
        story = prompt.split("STORY (untrusted data):\n", 1)[1].split("\nSCENES:", 1)[0]
        story = story.split("\nPartition", 1)[0]
        blocks = re.findall(r"(?ms)^\[\d+\] (.*?)(?=\n\n\[\d+\] |\Z)", story)
        if schema is Segmentation:
            return Segmentation(
                scenes=[
                    Scene(
                        first=0,
                        last=len(blocks) - 1,
                        characters=[
                            Presence(name="Ada", evidence=Quote(paragraph=1, text=blocks[1]))
                        ],
                    )
                ]
            )
        definitions = json.loads(prompt.split("FEATURE DEFINITIONS:\n", 1)[1])
        findings = []
        for definition in definitions:
            occurrences = []
            if definition["id"] in {"R02", "X23", "X24"}:
                indices = range(2, len(blocks) - 1) if definition["id"] == "R02" else [1]
                occurrences = [
                    Occurrence(
                        scene=0,
                        label="question-1",
                        explanation="Synthetic demo evidence",
                        evidence=[Quote(paragraph=i, text=blocks[i])],
                    )
                    for i in indices
                ]
            findings.append(
                FeatureFinding(feature=definition["id"], complete=True, occurrences=occurrences)
            )
        return Findings(features=findings)


def synthetic_run(
    directory: Path, number: int, *, baseline: bool = False, story_format: str = "narrative"
) -> Path:
    """Write artificial research inputs under a demo directory, never the real corpus."""
    directory.mkdir(parents=True, exist_ok=False)
    paragraphs = [f"# DEMOSTRACIÓN FICTICIA {number}", "Ada buscaba una llave."]
    paragraphs.extend(f"Ada encontró la pista número {i} en el jardín." for i in range(number + 1))
    paragraphs.append("Ada encontró la llave y abrió la puerta.")
    atomic_write_text(directory / "story.md", "\n\n".join(paragraphs))
    fmt = "baseline" if baseline else story_format
    atomic_write_json(
        directory / "metadata.json",
        {
            "status": "completed",
            "story_format": fmt,
            "model": "SYNTHETIC-NO-NETWORK",
            "pipeline_version": "demo",
            "synthetic": True,
        },
    )
    atomic_write_json(directory / "generation_options.json", {"story_format": fmt})
    atomic_write_json(directory / "generator_version.json", {"generator_version": "DEMO-1"})
    atomic_write_json(directory / "request.json", {"original_prompt": f"SYNTHETIC-{number}"})
    return directory


def voted_study(root: Path, *, stories: int = 6, readers: int = 4):
    """Build an open study whose readers each vote until done: the longer story wins."""
    from asg_evaluation.study import StudyRepository

    repository = StudyRepository(root / "study.sqlite3")
    people = [repository.participant(f"reader-{i}") for i in range(readers)]
    repository.mark_author("reader-0")
    for i in range(stories):
        run = synthetic_run(root / "runs" / f"synthetic-{i:02}", i, baseline=i < 2)
        repository.add_story(run, owner=people[i - 2] if 2 <= i < 2 + readers else None)
    repository.open()
    for reader in people:
        while question := repository.next_question(reader):
            for side in ("left", "right"):
                repository.mark_read(reader, question["id"], question[side]["id"])
            longer = len(question["left"]["text"]) > len(question["right"]["text"])
            repository.vote(reader, question["id"], "A" if longer else "B")
    return repository
