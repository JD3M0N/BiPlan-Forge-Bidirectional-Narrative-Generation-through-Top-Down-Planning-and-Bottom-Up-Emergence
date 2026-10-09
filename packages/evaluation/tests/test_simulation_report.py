import json

from asg_evaluation import usage_cli
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


def test_a_figure_a_run_never_recorded_is_not_measured_rather_than_zero(tmp_path) -> None:
    """A 7.0 run has no compression_ratio; reading it as 0 would flatter the older corpus."""
    root = tmp_path / "Stories" / "Stagecraft"
    write_run(root, "old")
    write_run(root, "new", compression_ratio=0.8)
    records = {record.run_id: record for record in collect_simulations(tmp_path / "Stories")}
    assert records["old"].values["compression_ratio"] is None
    summary = summarize_simulations(records.values(), SIMULATION_GROUPINGS["memory"])[0]
    assert summary.values["compression_ratio"] == (0.8, 0.8)
    alone = summarize_simulations([records["old"]], SIMULATION_GROUPINGS["memory"])[0]
    assert alone.values["compression_ratio"] == (None, None)


def test_an_unmeasured_figure_is_an_empty_csv_cell(tmp_path) -> None:
    root = tmp_path / "Stories" / "Stagecraft"
    write_run(root, "old")
    destination = tmp_path / "simulations.csv"
    assert main(["--stories", str(tmp_path / "Stories"), "--csv", str(destination)]) == 0
    header, row = destination.read_text(encoding="utf-8").splitlines()
    cells = dict(zip(header.split(","), row.split(","), strict=True))
    assert cells["compression_ratio"] == ""
    assert cells["beats_forced"] == "2.0"


def test_partial_performance_is_reported_without_inventing_final_metrics(tmp_path) -> None:
    root = tmp_path / "Stories" / "Stagecraft"
    run = write_run(root, "interrumpida")
    (run / "simulation_metrics.json").unlink()
    metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    metadata["status"] = "failed"
    (run / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    stage = run / "stage" / "chapter-1-scene-1"
    stage.mkdir(parents=True)
    (stage / "turns.jsonl").write_text(
        json.dumps(
            {
                "id": "turn-1",
                "kind": "actor",
                "actor_id": "ana",
                "addressed_to": ["bruno"],
                "retrieved_memory_ids": ["ana-m1"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    records = collect_simulations(tmp_path / "Stories")
    assert len(records) == 1
    assert records[0].status == "failed"
    assert records[0].values["logged_turns"] == 1
    assert records[0].values["beats_forced"] is None
    assert records[0].values["logged_attempts"] is None
    assert records[0].values["logged_contexts"] is None
    assert records[0].values["context_coverage"] is None


def test_llm_usage_splits_calls_by_agent_and_leaves_older_logs_unmeasured(tmp_path, capsys) -> None:
    def call(call_id, agent, status="succeeded", tokens=10, **extra):
        record = {"call_id": call_id, "operation": "structured:X", "stage": "performance"}
        record.update(status=status, total_tokens=tokens, duration_seconds=1.5, **extra)
        return record | ({} if agent is None else {"agent": agent})

    logs = {
        "nueva": [
            call("a", "actor", status="failed", tokens=0, wait_seconds=2.0),
            call("a", "actor"),
            call("b", "actor"),
            call("c", "stage_manager"),
            {"operation": "count_tokens", "agent": "actor", "call_id": "z", "total_tokens": 99},
        ],
        "vieja": [call("d", None)],
    }
    root = tmp_path / "Stories" / "Stagecraft"
    for name, records in logs.items():
        run = write_run(root, name)
        lines = "".join(json.dumps(record) + "\n" for record in records)
        (run / "llm_calls.jsonl").write_text(lines, encoding="utf-8")
    destination = tmp_path / "usage.csv"
    args = ["--stories", str(tmp_path / "Stories"), "--csv", str(destination), "--group", "agent"]
    assert usage_cli.main(args) == 0
    output = capsys.readouterr().out
    assert "Hybrid por agente  (1 run medido, 1 no medido)" in output
    actor = next(line.split() for line in output.splitlines() if line.strip().startswith("actor"))
    # calls, share, attempts, failed, tokens, latency, wait
    assert actor[1:] == ["2", "66.7", "3", "1", "20", "4.5", "2.0"]
    rows = destination.read_text(encoding="utf-8").splitlines()
    assert [row.split(",")[0] for row in rows[1:]] == ["nueva", "nueva", "vieja"]
    assert rows[-1].endswith(",,,,,,,")
