"""Offline end-to-end demonstration with explicitly synthetic stories and preferences."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text, use_utf8_output

from .feature_report import horizontal_report, read_features
from .features import (
    FeatureFinding,
    Findings,
    Occurrence,
    Presence,
    Quote,
    Scene,
    Segmentation,
    extract_features,
)
from .judge import rank_features, train_judge
from .preferences import human_report
from .study import StudyRepository


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


def synthetic_run(directory: Path, number: int, *, baseline: bool = False) -> Path:
    """Write artificial research inputs under a demo directory, never the real corpus."""
    directory.mkdir(parents=True, exist_ok=False)
    paragraphs = [f"# DEMOSTRACIÓN FICTICIA {number}", "Ada buscaba una llave."]
    paragraphs.extend(f"Ada encontró la pista número {i} en el jardín." for i in range(number + 1))
    paragraphs.append("Ada encontró la llave y abrió la puerta.")
    atomic_write_text(directory / "story.md", "\n\n".join(paragraphs))
    fmt = "baseline" if baseline else "narrative"
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


def prepare_demo(output: Path, *, readers: int = 6) -> StudyRepository:
    """Create five curated stories plus one per artificial participant and freeze them."""
    if output.exists():
        raise ValueError("Elige una carpeta nueva para no sobrescribir una demostración.")
    output.mkdir(parents=True)
    repository = StudyRepository(output / "study.sqlite3")
    repository.create("SYNTHETIC-DEMO", required_version="DEMO-1")
    repository.transition("collection")
    people = [
        repository.participant(f"synthetic-reader-{i}", profile="synthetic", is_author=i == 0)
        for i in range(readers)
    ]
    for i in range(5 + readers):
        run = synthetic_run(output / "runs" / f"synthetic-{i:02}", i, baseline=i < 2)
        repository.add_story(run, curated=i < 5, owner=people[i - 5]["id"] if i >= 5 else None)
    repository.freeze()
    repository.transition("evaluation")
    return repository


def synthetic_votes(repository: StudyRepository) -> None:
    """Exercise reading and voting transitions with deterministic nonhuman preferences."""
    for reader in repository.export()["participants"]:
        while question := repository.next_question(reader["id"]):
            for side in ("left", "right"):
                repository.mark_read(reader["id"], question["id"], question[side]["id"])
            choice = "A" if len(question["left"]["text"]) > len(question["right"]["text"]) else "B"
            if question["position"] == 1:
                choice = "abstain"
            repository.vote(reader["id"], question["id"], choice)


def run_demo(output: Path, *, bootstrap: int = 20) -> dict:
    """Demonstrate storage, evidence, aggregation, validation and ranking entirely offline."""
    repository = prepare_demo(output)
    synthetic_votes(repository)
    dataset = repository.export()
    provider = SyntheticProvider()
    features = {}
    for story in dataset["stories"]:
        report = extract_features(
            story["text"],
            provider,
            model="SYNTHETIC-NO-NETWORK",
            output=output / "features" / f"{story['id']}.json",
        )
        features[story["id"]] = report
    human = human_report(dataset, bootstrap=bootstrap)
    judge = train_judge(dataset, features)
    rows = []
    for story in dataset["stories"]:
        report = features[story["id"]]
        row = {
            "story": story["id"],
            "status": "completed",
            "format": story["provenance"]["metadata"]["story_format"],
            "generator_version": "DEMO-1",
            "pipeline_version": "demo",
            "extraction_compatible": True,
            "features": report["features"],
        }
        rows.append(row)
    ranking = rank_features(judge, rows)
    for name, data in (
        ("study.json", dataset),
        ("human.json", human),
        ("judge.json", judge),
        ("ranking.json", ranking),
    ):
        atomic_write_json(output / name, {**data, "synthetic": True})
    process_rows = [read_features(p.parent) for p in sorted((output / "runs").rglob("story.md"))]
    atomic_write_json(
        output / "horizontal.json", {**horizontal_report(process_rows), "synthetic": True}
    )
    summary = {
        "synthetic": True,
        "stories": len(dataset["stories"]),
        "votes": len(dataset["votes"]),
        "provider_calls_fake": provider.calls,
        "network_calls": 0,
        "criteria": {k: v["status"] for k, v in judge["criteria"].items()},
    }
    atomic_write_json(output / "summary.json", summary)
    atomic_write_text(
        output / "README.md",
        "# Demostración con datos ficticios\n\n"
        "Ninguna historia, preferencia ni puntuación de esta carpeta es un resultado "
        "experimental. El proveedor es local y no utiliza la red.\n",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    """Run a self-contained offline demonstration in a new directory."""
    parser = argparse.ArgumentParser(description="Demostración ficticia de evaluación, sin red")
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    use_utf8_output()
    print(json.dumps(run_demo(args.output), ensure_ascii=False, indent=2))
    return 0
