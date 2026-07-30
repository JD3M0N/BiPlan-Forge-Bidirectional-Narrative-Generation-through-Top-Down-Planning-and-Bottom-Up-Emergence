from unittest.mock import Mock

from asg_telegram import launcher


def test_windows_launcher_opens_a_new_console(monkeypatch):
    process = Mock()
    monkeypatch.setattr(launcher.os, "name", "nt")
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    monkeypatch.setattr(launcher.subprocess, "CREATE_NEW_CONSOLE", 16, raising=False)
    monkeypatch.setattr(launcher, "launch_command", lambda: ["python", "-m", "bot"])

    assert launcher.main() == 0
    process.assert_called_once_with(
        ["python", "-m", "bot"],
        creationflags=16,
        close_fds=True,
    )


def test_launcher_reports_console_creation_error(monkeypatch):
    monkeypatch.setattr(launcher.os, "name", "nt")
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        Mock(side_effect=OSError("boom")),
    )
    assert launcher.main() == 1
