import json

from asg_evaluation.pairing import pair_runs, read_run_config, run_measurements


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def run_73(root, name, *, memory="own", prompt="Una historia", voice="omniscient"):
    run = root / name
    options = {
        "story_format": "simulated",
        "script_method": "native",
        "narrative_profile": "essential",
        "narrative_guidance": True,
        "promise_ledger": True,
        "audio": True,
        "audio_voice": "",
        "narrative_voice": voice,
        "narrator": "",
        "narration_tone": "",
        "actor_memory": memory,
        "turns_per_beat": 8,
    }
    write(run / "generation_options.json", options)
    write(run / "metadata.json", {"status": "completed", "pipeline_version": "7.3", "model": "m"})
    write(run / "request.json", {"original_prompt": prompt, "title": "T"})
    write(run / "simulation_metrics.json", {"beats_forced": 1, "repetition_ratio": 0.1})
    (run / "story.md").write_text("# El faro\n\nTexto.", encoding="utf-8")
    return run


def run_72(root, name):
    run = root / name
    write(
        run / "metadata.json",
        {
            "status": "completed",
            "pipeline_version": "7.2",
            "model": "m",
            "story_format": "simulated",
            "narrative_voice": "omniscient",
            "actor_memory": "own",
            "narrative_profile": "essential",
        },
    )
    write(run / "request.json", {"original_prompt": "Una historia"})
    write(run / "performance.json", {"settings": {"turns_per_beat": 8}})
    return run


def test_two_runs_that_differ_only_in_memory_are_a_clean_pair(tmp_path) -> None:
    own = run_73(tmp_path, "a")
    shared = run_73(tmp_path, "b", memory="shared")
    pairing = pair_runs([own, shared])
    assert pairing.differing_axes == ["actor_memory"]
    assert pairing.clean
    assert pairing.metrics["beats_forced"] == [1.0, 1.0]
    assert any("indicio" in item for item in pairing.warnings)


def test_different_works_are_never_a_clean_pair(tmp_path) -> None:
    pairing = pair_runs(
        [run_73(tmp_path, "a"), run_73(tmp_path, "b", prompt="Otra", memory="shared")]
    )
    assert "work" in pairing.differing_axes
    assert not pairing.clean
    assert any("obras distintas" in item for item in pairing.warnings)


def test_an_older_run_rebuilds_its_axes_and_keeps_the_unrecorded_ones_unknown(tmp_path) -> None:
    config = read_run_config(run_72(tmp_path, "old"))
    assert config.axes["turns_per_beat"] == 8
    assert config.axes["narrator"] == ""
    assert config.axes["promise_ledger"] is None
    assert config.sources["turns_per_beat"] == "performance.json"
    pairing = pair_runs([run_72(tmp_path, "old"), run_73(tmp_path, "new")])
    assert "promise_ledger" in pairing.unknown_axes
    assert pairing.differing_axes == []


def test_a_figure_a_run_never_recorded_is_none_not_zero(tmp_path) -> None:
    values = run_measurements(run_72(tmp_path, "old"))
    assert values["beats_forced"] is None
    assert values["story_words"] is None
