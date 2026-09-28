from unittest.mock import Mock

from asg_telegram import launcher


def test_windows_launcher_opens_a_console_or_reports_the_failure(monkeypatch):
    """A new console is opened with the expected flags; an OSError becomes exit code 1."""
    process = Mock()
    monkeypatch.setattr(launcher.os, "name", "nt")
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    monkeypatch.setattr(launcher.subprocess, "CREATE_NEW_CONSOLE", 16, raising=False)
    monkeypatch.setattr(launcher, "launch_command", lambda: ["python", "-m", "bot"])

    assert launcher.main([]) == 0
    process.assert_called_once_with(
        ["python", "-m", "bot"],
        creationflags=16,
        close_fds=True,
    )

    monkeypatch.setattr(launcher.subprocess, "Popen", Mock(side_effect=OSError("boom")))
    assert launcher.main([]) == 1


def test_launch_command_runs_the_hosted_launcher():
    assert launcher.launch_command()[1:] == ["-m", "asg_telegram.launcher", "--hosted"]


def test_run_hosted_does_not_pause_on_a_clean_exit():
    prompts: list[str] = []
    code = launcher.run_hosted(run_bot=lambda argv: 0, input_fn=prompts.append)
    assert code == 0
    assert prompts == []


def test_run_hosted_pauses_on_a_reported_failure():
    prompts: list[str] = []
    code = launcher.run_hosted(run_bot=lambda argv: 2, input_fn=prompts.append)
    assert code == 2
    assert prompts


def test_run_hosted_pauses_after_an_unexpected_exception():
    def boom(argv):
        raise RuntimeError("se rompió el arranque")

    prompts: list[str] = []
    code = launcher.run_hosted(run_bot=boom, input_fn=lambda prompt: prompts.append(prompt))
    assert code == 1
    assert prompts


def test_run_hosted_exits_clean_on_keyboard_interrupt():
    def interrupted(argv):
        raise KeyboardInterrupt

    prompts: list[str] = []
    code = launcher.run_hosted(run_bot=interrupted, input_fn=lambda prompt: prompts.append(prompt))
    assert code == 0
    assert prompts == []


def test_run_hosted_tolerates_an_eof_while_waiting():
    def eof_input(prompt):
        raise EOFError

    code = launcher.run_hosted(run_bot=lambda argv: 2, input_fn=eof_input)
    assert code == 2
