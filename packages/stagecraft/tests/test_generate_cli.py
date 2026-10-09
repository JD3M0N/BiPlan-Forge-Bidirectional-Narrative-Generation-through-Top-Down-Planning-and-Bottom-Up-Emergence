from types import SimpleNamespace

import pytest
from asg_stagecraft import CastMember, GenerationOptions, StoryBrief
from asg_stagecraft.formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.runtime.config import Settings
from asg_stagecraft.tools.generate import (
    apply_setting_flags,
    build_options,
    main,
    parser,
    read_request,
)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["--profile", "expansive", "--model", "gemini-3.5-pro", "--no-audio"],
            {"profile": NarrativeProfile.EXPANSIVE, "model": "gemini-3.5-pro", "no_audio": True},
        ),
        (
            ["--format", "script", "--script-method", "adapted"],
            {"story_format": StoryFormat.SCRIPT, "script_method": ScriptMethod.ADAPTED},
        ),
        (
            [],
            {"story_format": None, "script_method": None},
        ),
    ],
    ids=["experiment-flags", "output-format-flags", "output-format-defaults-to-settings"],
)
def test_flags_are_parsed(argv, expected) -> None:
    args = parser().parse_args(["Escribe una historia", *argv])
    assert args.prompt == "Escribe una historia"
    for attribute, value in expected.items():
        assert getattr(args, attribute) == value


def test_output_flag_sets_the_run_directory() -> None:
    args = parser().parse_args(["Escribe una historia", "--output", "runs/batch"])
    assert args.output.name == "batch"


def test_the_model_flags_outrank_the_settings_for_this_run(tmp_path) -> None:
    base = Settings(api_key="k", model="gemini-3.5-flash-lite", output_root=tmp_path)
    args = parser().parse_args(["Escribe una historia", "--stage-model", "gemini-3.1-flash-lite"])
    changed = apply_setting_flags(args, base)
    assert (changed.model, changed.stage_model, changed.output_root) == (
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        tmp_path,
    )
    assert changed.splits_stage and not base.splits_stage


@pytest.mark.parametrize(
    "argv",
    [
        ["--profile", "epica"],
        ["--format", "screenplay"],
        ["--audio-voice", "es-XX-NadieNeural"],
    ],
    ids=["unknown-profile", "unknown-format", "unknown-audio-voice"],
)
def test_an_unknown_choice_is_rejected_by_the_parser(argv) -> None:
    with pytest.raises(SystemExit):
        parser().parse_args(["Escribe una historia", *argv])


def settings(**fields):
    values = {
        "narrative_guidance": True,
        "promise_ledger": True,
        "story_format": StoryFormat.NARRATIVE,
        "script_method": ScriptMethod.NATIVE,
        "narrative_voice": NarrativeVoice.OMNISCIENT,
        "actor_memory": ActorMemory.OWN,
        "turns_per_beat": 8,
    }
    return SimpleNamespace(**{**values, **fields})


def test_the_narration_flags_reach_the_run_options() -> None:
    args = parser().parse_args(
        [
            "Escribe una historia",
            "--format",
            "simulated",
            "--voice",
            "limited",
            "--narrator",
            "Ana",
            "--tone",
            "como un guerrero samurai",
            "--turns-per-beat",
            "5",
            "--audio-voice",
            "es-CU-BelkysNeural",
            "--guidance-strategy",
            "compositional_v2",
            "--no-narrative-guidance",
        ]
    )
    options = build_options(args, settings())
    assert options.story_format is StoryFormat.SIMULATED
    assert options.narrative_voice is NarrativeVoice.LIMITED
    assert options.narrator == "Ana"
    assert options.narration_tone == "como un guerrero samurai"
    assert options.turns_per_beat == 5
    assert options.audio_voice == "es-CU-BelkysNeural"
    assert options.guidance_strategy == "compositional_v2"
    assert options.narrative_guidance is False


def test_a_recorded_options_file_replays_a_run_and_flags_still_win(tmp_path) -> None:
    recorded = GenerationOptions(
        story_format=StoryFormat.SIMULATED,
        narrative_voice=NarrativeVoice.FIRST_PERSON,
        narrator="Ana",
        promise_ledger=False,
    )
    path = tmp_path / "generation_options.json"
    path.write_text(recorded.model_dump_json(), encoding="utf-8")
    args = parser().parse_args(
        ["Escribe una historia", "--options", str(path), "--actor-memory", "shared"]
    )
    # Today's settings say narrative; the recorded run said simulated, and the file wins.
    options = build_options(args, settings(story_format=StoryFormat.SCRIPT))
    assert options == recorded.with_changes(actor_memory=ActorMemory.SHARED)


def test_a_brief_file_is_read_as_the_request(tmp_path) -> None:
    brief = StoryBrief(plot="Una trama.", cast=[CastMember(name="Ana")])
    path = tmp_path / "brief.json"
    path.write_text(brief.model_dump_json(), encoding="utf-8")
    assert read_request(parser().parse_args(["--brief", str(path)])) == brief
    assert read_request(parser().parse_args(["  Una historia  "])) == "Una historia"


def test_a_prompt_and_a_brief_together_are_refused(tmp_path, capsys) -> None:
    assert main(["Una historia", "--brief", str(tmp_path / "brief.json")]) == 2
    assert "--brief" in capsys.readouterr().err


def test_plan_from_selects_simulation_without_prompting() -> None:
    args = parser().parse_args(["--plan-from", "Stories/original", "--simulation-mode", "adaptive"])
    options = build_options(args, settings())
    assert read_request(args) == ""
    assert options.story_format is StoryFormat.SIMULATED
    assert options.simulation_mode.value == "adaptive"


@pytest.mark.parametrize(("force", "code"), [(False, 3), (True, 1)], ids=["refused", "forced"])
def test_a_run_without_quota_stops_before_its_first_call_unless_forced(
    monkeypatch, capsys, tmp_path, force, code
) -> None:
    import asg_stagecraft.tools.generate as generate_module

    def no_provider(_settings):
        raise ValueError("the forced run reached the provider")

    real = Settings(api_key="k", model="m", output_root=tmp_path)
    monkeypatch.setattr(generate_module, "load_settings", lambda: real)
    monkeypatch.setattr(generate_module, "preflight", lambda *_: "queda 0")
    monkeypatch.setattr(generate_module, "provider_from_settings", no_provider)
    assert main(["Una historia", *(["--force"] if force else [])]) == code
    assert ("queda 0" in capsys.readouterr().err) is not force
