from collections import Counter
import json
import re

from pydantic import BaseModel

from asg_top_down.schemas import (
    ArchetypeSelection, ChapterComplianceArtifact, ChapterPlan, Character,
    CharactersArtifact, DirectedStoryArtifact, FreytagPhaseAssessment,
    FreytagReviewArtifact, NarrativeEdge, NodeGoal, PlotNode, ReviewArtifact,
    StoryPlanArtifact, StoryRequest, WorldArtifact,
)


def _directed() -> DirectedStoryArtifact:
    phases = ["exposition", "rising_action", "climax", "falling_action", "denouement"]
    chapters, nodes, edges = [], [], []
    previous = None
    order = 1
    for chapter_order, phase in enumerate(phases, 1):
        chapter_id = f"chapter_{chapter_order}"
        chapters.append(ChapterPlan(id=chapter_id, order=chapter_order, title=f"Parte {chapter_order}", abstract=phase, target_words=300, freytag_phases=[phase]))
        for local, kind in enumerate(("CBN", "CPN", "CEN"), 1):
            node_id = f"node_{order}"
            nodes.append(PlotNode(
                id=node_id, chapter_id=chapter_id, node_type=kind,
                subject="Ada", verb=("descubre" if kind == "CPN" else "avanza"),
                object=f"evento {order}", timestamp=order - 1, global_order=order,
                local_order=local, target_words=100,
                goals=[NodeGoal(purpose=f"Realizar {phase}", archetype_id="discovery", taxonomy_beat="investigation", success_criteria=["El evento aparece"])],
            ))
            if previous:
                edges.append(NarrativeEdge(source=previous, target=node_id, relation="causes", strength=5, rationale="Progresión"))
            previous = node_id
            order += 1
    return DirectedStoryArtifact(chapters=chapters, nodes=nodes, candidate_edges=edges)


RESPONSES: dict[type[BaseModel], BaseModel] = {
    StoryRequest: StoryRequest(original_prompt="Una historia", title="La señal", genre="ciencia ficción", tone="melancólico", premise="Una señal cambia una vida."),
    StoryPlanArtifact: StoryPlanArtifact(logline="Ada descifra una señal.", theme="Confianza", central_conflict="Verdad contra incredulidad", progression=["Descubre", "Pierde", "Comprende"], intended_ending="Comparte el mensaje.", archetypes=ArchetypeSelection(primary="discovery", secondary=["mystery"], confidence=.9, prompt_evidence=["señal"], rationale="La verdad transforma a Ada.")),
    WorldArtifact: WorldArtifact(setting="Una estación orbital", time_period="Futuro", rules=["La comunicación tarda"], locations=["Observatorio"], atmosphere="Decadente"),
    CharactersArtifact: CharactersArtifact(characters=[Character(name="Ada", narrative_role="protagonista", jungian_archetype="explorer", goal="Descifrar", motivation="Comprender", conflict="Nadie le cree", arc="Aprende a confiar")]),
    DirectedStoryArtifact: _directed(),
    FreytagReviewArtifact: FreytagReviewArtifact(passed=True, phases=[FreytagPhaseAssessment(phase=phase, present=True, chapter_ids=[f"chapter_{i}"], node_ids=[f"node_{i * 3 - 1}"], intensity=min(10, i + 4), evidence="Presente") for i, phase in enumerate(["exposition", "rising_action", "climax", "falling_action", "denouement"], 1)]),
    ReviewArtifact: ReviewArtifact(coherence_score=8, continuity_score=8, style_score=7, compliance_score=9, archetype_score=8, graph_coverage_score=9, strengths=["Clara"], issues=[], revision_instructions=[]),
}


class FakeProvider:
    model_name = "fake-flash"

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls = []
        self.text_calls = Counter()
        self.fail_on = fail_on

    def generate_structured(self, *, system_instruction: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
        self.calls.append(("structured", schema.__name__))
        if self.fail_on == schema.__name__:
            raise RuntimeError("fallo simulado")
        if schema.__name__ == "SemanticArchetypeRanking":
            catalog = json.loads(prompt.split("CATALOGO:\n", 1)[1])
            return schema.model_validate({"scores": [{"archetype_id": x["id"], "relevance": .9 if x["id"] in {"discovery", "mystery"} else .1} for x in catalog]})
        if schema is ChapterComplianceArtifact:
            ids = sorted(set(re.findall(r'"id": "(node_\d+)"', prompt)), key=lambda x: int(x.split("_")[1]))
            return ChapterComplianceArtifact(passed=True, actual_words=300, covered_node_ids=ids, covered_goals=["all"])
        return RESPONSES[schema].model_copy(deep=True)

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        kind = "story" if "editor literario" in system_instruction else "scene"
        self.calls.append(("text", kind))
        self.text_calls[kind] += 1
        if self.fail_on == kind:
            raise RuntimeError("fallo simulado")
        count = 1500 if kind == "story" else 300
        return " ".join(["palabra"] * count)
