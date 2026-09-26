import json

from asg_evaluation.report import _describe
from asg_evaluation.simulation_cli import main, parser
from asg_evaluation.simulation_report import (
    SIMULATION_GROUPINGS,
    collect_simulations,
    summarize_simulations,
)


def write_run(root, name, *, story_format="simulated", voice="omniscient", memory="own", **metrics):
    run = root / name
    run.mkdir(parents=True)
    (run / "story.md").write_text("# Historia\n\n## Uno\n\nTexto.\n", encoding="utf-8")
    (run / "metadata.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "story_format": story_format,
                "narrative_voice": voice if story_format == "simulated" else None,
                "actor_memory": memory if story_format == "simulated" else None,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    (run / "generator_version.json").write_text(
        json.dumps({"generator_version": "7.0.0", "pipeline_version": "7.0"}), encoding="utf-8"
    )
    if story_format == "simulated":
        base = {
            "narrative_profile": "essential",
            "narrative_voice": voice,
            "actor_memory": memory,
            "scenes": 4,
            "turns": 40,
            "beats": 8,
            "beat_completion_ratio": 0.75,
            "beats_forced": 2,
            "turns_per_beat": 5.0,
            "unknown_mentions": 1,
        }
        base.update(metrics)
        (run / "simulation_metrics.json").write_text(json.dumps(base), encoding="utf-8")
    return run


def test_a_simulated_run_is_grouped_as_hybrid(tmp_path) -> None:
    root = tmp_path / "Stories"
    simulated = write_run(root / "Stagecraft", "20260101-000000-una")
    _, approach, _, _, _ = _describe(simulated, root)
    assert approach == "Hybrid"


def test_a_narrative_run_under_the_same_folder_stays_top_down(tmp_path) -> None:
    root = tmp_path / "Stories"
    narrative = write_run(root / "Stagecraft", "20260101-000001-otra", story_format="narrative")
    _, approach, _, _, _ = _describe(narrative, root)
    assert approach == "Top-Down"


def test_the_pre_rename_corpus_keeps_its_approach(tmp_path) -> None:
    root = tmp_path / "Stories"
    legacy = root / "Top-Down" / "20250101-000000-vieja"
    legacy.mkdir(parents=True)
    (legacy / "story.md").write_text("# Vieja\n", encoding="utf-8")
    _, approach, _, _, _ = _describe(legacy, root)
    assert approach == "Top-Down"


def test_collecting_reads_every_axis_and_ignores_runs_without_a_performance(tmp_path) -> None:
    root = tmp_path / "Stories" / "Stagecraft"
    write_run(root, "a", voice="focalized", memory="shared")
    write_run(root, "b", story_format="narrative")
    records = collect_simulations(tmp_path / "Stories")
    assert len(records) == 1
    assert records[0].narrative_voice == "focalized"
    assert records[0].actor_memory == "shared"
    assert records[0].generator_version == "7.0.0"
    assert records[0].values["beats_forced"] == 2


def test_summaries_group_by_the_axes_the_thesis_turns(tmp_path) -> None:
    root = tmp_path / "Stories" / "Stagecraft"
    write_run(root, "a", memory="own", unknown_mentions=1)
    write_run(root, "b", memory="own", unknown_mentions=3)
    write_run(root, "c", memory="shared", unknown_mentions=9)
    records = collect_simulations(tmp_path / "Stories")
    summaries = {
        item.label: item for item in summarize_simulations(records, SIMULATION_GROUPINGS["memory"])
    }
    assert summaries["own"].runs == 2
    assert summaries["own"].values["unknown_mentions"] == (2.0, 2.0)
    assert summaries["shared"].values["unknown_mentions"] == (9.0, 9.0)


def test_the_cli_writes_a_csv_and_reports_every_axis(tmp_path, capsys) -> None:
    root = tmp_path / "Stories" / "Stagecraft"
    write_run(root, "a")
    destination = tmp_path / "simulations.csv"
    assert main(["--stories", str(tmp_path / "Stories"), "--csv", str(destination)]) == 0
    rows = destination.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("story,run_id,narrative_profile,narrative_voice,actor_memory")
    assert len(rows) == 2
    output = capsys.readouterr().out
    for axis in ("voice", "memory", "profile", "version"):
        assert f"Agrupado por {axis}" in output


def test_the_cli_says_so_when_nothing_has_been_performed(tmp_path, capsys) -> None:
    assert main(["--stories", str(tmp_path)]) == 0
    assert "No hay funciones que resumir" in capsys.readouterr().out


def test_the_parser_offers_every_grouping(tmp_path) -> None:
    args = parser().parse_args(["--group", "voice-memory"])
    assert args.group == "voice-memory"
