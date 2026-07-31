from asg_prompt_crafter.schemas import CraftResult, PromptAlternative

def sample_result(original_prompt: str = "Un caballero salva a una princesa") -> CraftResult:
    return CraftResult(
        original_prompt=original_prompt,
        alternatives=[
            PromptAlternative(id="epica", name="Épica crepuscular", creative_direction="Fantasía heroica con coste moral.", prompt="Escribe una epopeya sobre el rescate y su coste moral."),
            PromptAlternative(id="intriga", name="Intriga cortesana", creative_direction="El rescate encubre una conspiración.", prompt="Escribe una intriga en la que el rescate revela una conspiración."),
            PromptAlternative(id="dragon", name="La voz del dragón", creative_direction="La criatura tiene motivos comprensibles.", prompt="Escribe el rescate mostrando también los motivos del dragón."),
        ],
        recommended_id="intriga",
        recommendation_reason="Ofrece el conflicto más rico.",
    )

class FakeProvider:
    model_name = "fake-model"
    def __init__(self, result: CraftResult | None = None) -> None:
        self.result = result or sample_result()
        self.calls: list[dict[str, object]] = []
    def generate_structured(self, **kwargs: object) -> CraftResult:
        self.calls.append(kwargs)
        return self.result.model_copy(deep=True)
