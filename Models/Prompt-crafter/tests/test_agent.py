import pytest
from pydantic import ValidationError
from asg_prompt_crafter import PromptCrafterAgent
from asg_prompt_crafter.schemas import CraftResult
from prompt_crafter_fakes import FakeProvider, sample_result

def test_craft_returns_three_alternatives_and_preserves_original() -> None:
    provider = FakeProvider(sample_result("Texto alterado por el proveedor"))
    result = PromptCrafterAgent(provider).craft("  Un caballero salva a una princesa  ")
    assert result.original_prompt == "Un caballero salva a una princesa"
    assert len(result.alternatives) == 3
    assert result.recommended_id == "intriga"
    assert len(provider.calls) == 1
    assert provider.calls[0]["prompt"] == "Un caballero salva a una princesa"
    assert provider.calls[0]["schema"] is CraftResult

def test_instruction_requests_diversity_fidelity_and_top_down_readiness() -> None:
    provider = FakeProvider()
    PromptCrafterAgent(provider).craft("Una aventura")
    instruction = str(provider.calls[0]["system_instruction"])
    for phrase in ("exactamente tres", "sustancialmente diferentes", "no contradecir", "Top-Down", "autocontenido"):
        assert phrase in instruction

def test_empty_prompt_is_rejected_without_calling_provider() -> None:
    provider = FakeProvider()
    with pytest.raises(ValueError, match="vacío"):
        PromptCrafterAgent(provider).craft("  ")
    assert provider.calls == []

@pytest.mark.parametrize("change", [
    lambda data: data["alternatives"].__setitem__(1, data["alternatives"][0]),
    lambda data: data.__setitem__("recommended_id", "inexistente"),
    lambda data: data["alternatives"].pop(),
])
def test_result_rejects_invalid_alternatives(change) -> None:
    data = sample_result().model_dump()
    change(data)
    with pytest.raises(ValidationError):
        CraftResult.model_validate(data)
