import builtins
import pytest
from asg_prompt_crafter import cli
from asg_prompt_crafter.config import Settings
from asg_prompt_crafter.errors import ProviderError
from prompt_crafter_fakes import sample_result

class SuccessfulAgent:
    def __init__(self, provider: object) -> None: pass
    def craft(self, prompt: str): return sample_result(prompt)

def configure_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_settings", lambda: Settings("key", "fake-model"))
    monkeypatch.setattr(cli, "GeminiProvider", lambda *args: object())

def test_cli_prints_three_options_and_recommendation(monkeypatch, capsys) -> None:
    configure_cli(monkeypatch)
    monkeypatch.setattr(cli, "PromptCrafterAgent", SuccessfulAgent)
    monkeypatch.setattr(builtins, "input", lambda _: "Una aventura")
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "1. Épica crepuscular" in output
    assert "2. Intriga cortesana [intriga] — RECOMENDADA" in output
    assert "3. La voz del dragón" in output
    assert "Recomendación: Ofrece el conflicto más rico." in output

def test_cli_rejects_empty_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr(builtins, "input", lambda _: "  ")
    assert cli.main() == 2
    assert "no puede estar vacío" in capsys.readouterr().err

def test_cli_handles_cancellation(monkeypatch, capsys) -> None:
    def cancel(_: str) -> str: raise KeyboardInterrupt
    monkeypatch.setattr(builtins, "input", cancel)
    assert cli.main() == 1
    assert "operación cancelada" in capsys.readouterr().err

def test_cli_handles_provider_error(monkeypatch, capsys) -> None:
    class FailingAgent:
        def __init__(self, provider: object) -> None: pass
        def craft(self, prompt: str): raise ProviderError("sin conexión")
    configure_cli(monkeypatch)
    monkeypatch.setattr(cli, "PromptCrafterAgent", FailingAgent)
    monkeypatch.setattr(builtins, "input", lambda _: "Una aventura")
    assert cli.main() == 1
    assert "sin conexión" in capsys.readouterr().err
