from types import SimpleNamespace

import pytest
from asg_stagecraft import CastMember, GenerationOptions, StoryBrief
from asg_stagecraft.formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.tools.generate import build_options, main, parser, read_request


def test_experiment_flags_are_parsed() -> None:
    args = parser().parse_args(
        [
            "Escribe una historia",
            "--profile",
            "expansive",
            "--model",
            "gemini-3.5-pro",
            "--output",
            "runs/batch",
            "--no-audio",
        ]
    )
    assert args.prompt == "Escribe una historia"
    assert args.profile is NarrativeProfile.EXPANSIVE
    assert args.model == "gemini-3.5-pro"
    assert args.output.name == "batch"
    assert args.no_audio is True


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(SystemExit):
        parser().parse_args(["Escribe una historia", "--profile", "epica"])


def test_output_format_flags_are_parsed() -> None:
    args = parser().parse_args(
        ["Escribe una historia", "--format", "script", "--script-method", "adapted"]
    )
    assert args.story_format is StoryFormat.SCRIPT
    assert args.script_method is ScriptMethod.ADAPTED


def test_output_format_defaults_to_none_and_falls_back_to_settings() -> None:
    args = parser().parse_args(["Escribe una historia"])
    assert args.story_format is None
    assert args.script_method is None


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(SystemExit):
        parser().parse_args(["Escribe una historia", "--format", "screenplay"])


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
        ]
    )
    options = build_options(args, settings())
    assert options.story_format is StoryFormat.SIMULATED
    assert options.narrative_voice is NarrativeVoice.LIMITED
    assert options.narrator == "Ana"
    assert options.narration_tone == "como un guerrero samurai"
    assert options.turns_per_beat == 5
    assert options.audio_voice == "es-CU-BelkysNeural"


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


def test_an_unknown_audio_voice_is_rejected_by_the_parser() -> None:
    with pytest.raises(SystemExit):
        parser().parse_args(["Escribe una historia", "--audio-voice", "es-XX-NadieNeural"])


def test_a_prompt_and_a_brief_together_are_refused(tmp_path, capsys) -> None:
    assert main(["Una historia", "--brief", str(tmp_path / "brief.json")]) == 2
    assert "--brief" in capsys.readouterr().err
