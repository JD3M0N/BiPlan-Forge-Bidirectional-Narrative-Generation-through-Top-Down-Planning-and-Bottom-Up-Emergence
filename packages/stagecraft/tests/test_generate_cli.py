import pytest
from asg_stagecraft.formats import ScriptMethod, StoryFormat
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.tools.generate import parser


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
