import pytest
from asg_top_down.cli import parser
from asg_top_down.profiles import NarrativeProfile


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
