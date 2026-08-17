import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from asg_top_down.compare import build_comparison
from asg_top_down.agents import AnalystAgent
from asg_top_down.craft import (
    audit_questions, validate_craft_variant, validate_craft_variants,
)
from asg_top_down.errors import ArtifactValidationError, StorylinePlanningError
from asg_top_down.generator import StoryGenerator
from asg_top_down.incremental import IncrementalPlotPlanner
from asg_top_down.narrative_db import (
    CatalogEntry, NarrativeBlueprint, RetrievalTrace,
)
from asg_top_down.nekg import NarrativeEntityGraph
from asg_top_down.schemas import (
    ChapterAnchors, ChapterAnchorsArtifact, ChapterCraftLine, ChapterPlan,
    Character, CharacterMilestone, CharactersArtifact, CharacterSliderArc,
    CraftAuditAnswer, CraftAuditArtifact, CraftSelectionArtifact, CraftVariant,
    CraftVariantsArtifact, EntityStateChange, PPPLine, PPPPoint, PlotNode,
    PlotNodeProposal, PlotNodeReview, SliderRange, StoryOutlineArtifact,
    StoryPlanArtifact, StoryRequest, TryFailCycle, WorldArtifact,
)


def blueprint() -> NarrativeBlueprint:
    entries = {
        kind: [CatalogEntry(
            id=f"{kind}-1", kind=kind, name=kind, description=f"{kind} description",
            provenance="test",
        )]
        for kind in ("macroplot", "situation", "character_arc", "beat", "genre", "role")
    }
    trace = RetrievalTrace(query="test", selections=entries)
    return NarrativeBlueprint(
        macroplots=entries["macroplot"], situations=entries["situation"],
        character_arcs=entries["character_arc"], beats=entries["beat"],
        genres=entries["genre"], roles=entries["role"], trace=trace,
    )


class StaticRepository:
    def retrieve(self, _request):
        return blueprint()


def request() -> StoryRequest:
    return StoryRequest(
        original_prompt="Escribe en español y conserva una llave roja.",
        title="La llave", language="español", genre="fantasía", tone="tenso",
        target_words=700, premise="Lía busca una puerta antes del amanecer.",
        constraints=["La llave roja debe permanecer intacta."],
    )


def characters() -> CharactersArtifact:
    return CharactersArtifact(characters=[Character(
        name="Lía", narrative_role="protagonist", jungian_archetype="role-1",
        goal="Abrir la puerta", motivation="Salvar su barrio", conflict="El guardián se opone",
        arc="Aprende a actuar", importance="main",
        slider_arc=CharacterSliderArc(
            sympathy=SliderRange(start=8, target=9, rationale="Protege a otros"),
            competence=SliderRange(start=7, target=8, rationale="Conoce el mapa"),
            proactivity=SliderRange(start=2, target=8, rationale="Evita decidir"),
            focus="proactivity", justification="Cada decisión exige más iniciativa",
        ),
    )])


def outline() -> StoryOutlineArtifact:
    return StoryOutlineArtifact(
        premise="Una llave abre una verdad", synopsis="Lía encuentra y usa la llave.",
        chapters=[
            ChapterPlan(id="chapter-001", order=1, title="La señal", abstract="Encuentra la llave",
                        target_words=350, freytag_phases=["exposition", "rising_action"]),
            ChapterPlan(id="chapter-002", order=2, title="La puerta", abstract="Decide abrirla",
                        target_words=350, freytag_phases=["climax", "denouement"]),
        ],
    )


def line(identifier: str, kind: str = "master") -> PPPLine:
    return PPPLine(
        id=identifier, kind=kind, subject="La puerta prometida",
        promise=PPPPoint(chapter_id="chapter-001", description="La puerta puede salvar el barrio"),
        progress=[PPPPoint(chapter_id="chapter-001", description="La llave revela su precio")],
        payoff=PPPPoint(chapter_id="chapter-002", description="Lía abre la puerta pagando el precio"),
    )


def variant(identifier: str, subplot_count: int = 0) -> CraftVariant:
    subplots = [line(f"{identifier}-subplot-{index}", "character")
                for index in range(1, subplot_count + 1)]
    return CraftVariant(
        id=identifier,
        strategy={"variant-1": "Escalation through choice", "variant-2": "Escalation through cost",
                  "variant-3": "Escalation through revelation"}[identifier],
        master_line=line(f"{identifier}-master"),
        subplots=subplots,
        chapters=[
            ChapterCraftLine(
                chapter_id="chapter-001", promise="La llave ofrece una posibilidad",
                progress=["Lía prueba el primer mecanismo"], payoff="La puerta responde",
                advances_global_line_ids=[f"{identifier}-master"],
            ),
            ChapterCraftLine(
                chapter_id="chapter-002", promise="Abrir tendrá un costo",
                progress=["Lía asume el costo"], payoff="La puerta se abre sin romper la llave",
                advances_global_line_ids=[f"{identifier}-master"],
            ),
        ],
        character_milestones=[
            CharacterMilestone(character_name="Lía", chapter_id="chapter-001", stage="start",
                               description="Espera que otro tome la llave"),
            CharacterMilestone(character_name="Lía", chapter_id="chapter-001", stage="transition",
                               description="Decide probar el mecanismo"),
            CharacterMilestone(character_name="Lía", chapter_id="chapter-002", stage="end",
                               description="Abre la puerta por decisión propia"),
        ],
        try_fail_cycles=[
            TryFailCycle(id=f"{identifier}-try-1", chapter_id="chapter-001",
                         action="Prueba la llave", outcome="yes_but",
                         consequence="El guardián descubre su posición"),
            TryFailCycle(id=f"{identifier}-try-2", chapter_id="chapter-002",
                         action="Gira el mecanismo", outcome="no_and",
                         consequence="Pierde tiempo y debe comprometerse"),
        ],
    )


class V3Provider:
    model_name = "fake-v3"

    def __init__(self, fail_first_audit: bool = False):
        self.usage_records = []
        self.usage_callback = None
        self.wait_callback = None
        self.calls = []
        self.fail_first_audit = fail_first_audit
        self.audit_calls = 0
        self.writer_prompts = []

    def generate_structured(self, *, system_instruction, prompt, schema):
        self.calls.append((schema.__name__, system_instruction, prompt))
        if schema is StoryPlanArtifact:
            return StoryPlanArtifact(
                logline="Lía debe abrir una puerta", theme="La decisión crea esperanza",
                central_conflict="Lía contra el guardián", progression=["encuentra", "prueba", "decide"],
                intended_ending="La puerta se abre",
                archetypes={"primary": "macroplot-1", "secondary": ["situation-1"],
                            "confidence": .9, "rationale": "causal"},
            )
        if schema is WorldArtifact:
            return WorldArtifact(setting="Barrio amurallado", time_period="noche",
                                 rules=["La llave no puede copiarse"], locations=["puerta"], atmosphere="tensa")
        if schema is CharactersArtifact:
            return characters()
        if schema is StoryOutlineArtifact:
            return outline()
        if schema is ChapterAnchorsArtifact:
            return ChapterAnchorsArtifact(anchors=[
                ChapterAnchors(chapter_id="chapter-001", begin_subject="Lía", begin_verb="encuentra",
                               begin_object="la llave", end_subject="la puerta", end_verb="responde",
                               end_object="a Lía"),
                ChapterAnchors(chapter_id="chapter-002", begin_subject="Lía", begin_verb="entra",
                               begin_object="al umbral", end_subject="Lía", end_verb="abre",
                               end_object="la puerta"),
            ])
        if schema is PlotNodeProposal:
            chapter = "chapter-002" if '"id": "chapter-002"' in prompt else "chapter-001"
            return PlotNodeProposal(
                subject="Lía", verb="decide" if chapter == "chapter-002" else "prueba",
                object="el mecanismo", purpose="Avanzar hacia la puerta", schema_beat_id="beat-1",
                preconditions=["Lía conserva la llave"], effects=["El mecanismo cambia"],
                intention="Abrir la puerta", conflict="El guardián interfiere",
                state_changes=[EntityStateChange(entity="Lía", attribute="knowledge",
                                                 value="conoce el precio")],
            )
        if schema is PlotNodeReview:
            return PlotNodeReview(
                accepted=True, causal=True, intentional=True, conflict_present=True,
                continuous=True, novel=True, advances_ending=True, world_consistent=True,
                aligns_with_cen=True, review_focus=["logic"],
            )
        if schema is CraftVariantsArtifact:
            return CraftVariantsArtifact(variants=[
                variant("variant-1", 0), variant("variant-2", 1), variant("variant-3", 2),
            ])
        if schema is CraftSelectionArtifact:
            return CraftSelectionArtifact(selected_variant_id="variant-1", rationale="Best causal fit")
        if schema is CraftAuditArtifact:
            self.audit_calls += 1
            document = json.loads(prompt.split("QUESTIONS:\n", 1)[1].split("\n\nFICTION:", 1)[0])
            answers = []
            for question in document:
                fail = (self.fail_first_audit and self.audit_calls == 1
                        and question["question_id"] == "constraint:1")
                answers.append(CraftAuditAnswer(
                    **question, verdict="fail" if fail else "pass", evidence="Visible in the fiction",
                    issue="The red key breaks" if fail else "",
                    revision_instruction="Keep the red key intact" if fail else "",
                ))
            return CraftAuditArtifact(answers=answers, summary="reviewed")
        raise AssertionError(f"Unexpected schema: {schema.__name__}")

    def generate_text(self, *, system_instruction, prompt):
        self.calls.append(("text", system_instruction, prompt))
        if "literary rewriter" in system_instruction:
            body = " ".join(["La llave roja permanece intacta."] * 64)
            return f"## La señal\n\n{body}\n\n## La puerta\n\n{body}"
        self.writer_prompts.append(prompt)
        return " ".join(["Lía conserva la llave roja y actúa."] * 53)


def test_main_character_requires_two_high_one_low_and_ascending_focus():
    valid = characters().characters[0].slider_arc
    assert valid.focus == "proactivity"
    assert valid.proactivity.start == 2 and valid.proactivity.target == 8
    with pytest.raises(ValidationError):
        CharacterSliderArc(
            sympathy=SliderRange(start=8, target=9, rationale="x"),
            competence=SliderRange(start=6, target=8, rationale="x"),
            proactivity=SliderRange(start=2, target=8, rationale="x"),
            focus="proactivity", justification="x",
        )
    with pytest.raises(ValidationError):
        CharacterSliderArc(
            sympathy=SliderRange(start=8, target=9, rationale="x"),
            competence=SliderRange(start=7, target=8, rationale="x"),
            proactivity=SliderRange(start=2, target=6, rationale="x"),
            focus="proactivity", justification="x",
        )


def test_analyst_instruction_is_english_and_keeps_spanish_as_default_language():
    class AnalystProvider:
        def __init__(self):
            self.system_instruction = ""

        def generate_structured(self, *, system_instruction, prompt, schema):
            self.system_instruction = system_instruction
            return StoryRequest(
                original_prompt=prompt, title="Historia", language="español",
                genre="misterio", tone="tenso", premise="Una pista desaparece",
            )

    provider = AnalystProvider()
    result = AnalystAgent(provider, default_target_words=900).run("Escribe un misterio")
    assert result.language == "español"
    assert result.target_words == 900
    assert "narrative requirements analyst" in provider.system_instruction
    assert "Eres " not in provider.system_instruction


def test_node_contracts_contain_no_craft_fields():
    forbidden = {"promise", "progress", "payoff", "slider", "try_fail", "yes_but", "no_and"}
    for schema in (ChapterPlan, PlotNode, PlotNodeProposal, PlotNodeReview):
        names = {name.casefold() for name in schema.model_fields}
        assert not any(any(term in name for term in forbidden) for name in names)


def test_three_variants_are_distinct_complete_and_reject_node_references():
    artifact = CraftVariantsArtifact(variants=[
        variant("variant-1", 0), variant("variant-2", 1), variant("variant-3", 2),
    ])
    validate_craft_variants(artifact, outline(), characters(), 700)
    invalid = variant("variant-1").model_copy(deep=True)
    invalid.master_line.promise.description = "Use n_0001 as the promise"
    with pytest.raises(ValueError, match="cannot reference"):
        validate_craft_variant(invalid, outline(), characters(), 700)


def test_every_user_constraint_is_a_blocking_audit_question():
    questions = audit_questions(request(), variant("variant-1"), characters())
    constraint = next(item for item in questions if item["question_id"] == "constraint:1")
    assert constraint["blocking"] is True
    assert "llave roja" in constraint["question"].casefold()


def test_nekg_prioritizes_directed_pair_then_recent_incident_relations():
    graph = NarrativeEntityGraph()
    def node(identifier, subject, object_, timestamp):
        return PlotNode(
            id=identifier, chapter_id="chapter-001", node_type="CPN", subject=subject,
            verb="ve", object=object_, timestamp=timestamp, global_order=timestamp + 1,
            local_order=timestamp + 1, target_words=10,
            goals=[{"purpose": "x", "archetype_id": "x", "schema_beat_id": "x",
                    "success_criteria": ["x"]}],
        )
    graph.apply(node("n_0001", "Lía", "Puerta", 1))
    graph.apply(node("n_0002", "Puerta", "Lía", 9))
    graph.apply(node("n_0003", "Lía", "Guardián", 8))
    result = graph.related("Lía", "Puerta", limit=10)
    assert [item.plot_node_id for item in result] == ["n_0001", "n_0002", "n_0003"]


def test_generator_builds_variants_rewrites_blocking_failure_and_renders_without_replanning(tmp_path):
    provider = V3Provider(fail_first_audit=True)
    generator = StoryGenerator(
        provider, tmp_path, schema_repository=StaticRepository(),
        max_cpn_retries=1, max_craft_revisions=2,
    )
    run = generator.generate(request())
    root_story = run.story_path.read_text(encoding="utf-8")
    selection = (run.run_dir / "craft/selection.json").read_text(encoding="utf-8")
    assert (run.run_dir / "storyline.json").is_file()
    assert (run.run_dir / "craft/variants/variant-1/plan.json").is_file()
    assert (run.run_dir / "craft/variants/variant-2/plan.json").is_file()
    assert (run.run_dir / "craft/variants/variant-3/plan.json").is_file()
    assert not (run.run_dir / "craft/variants/variant-2/story.md").exists()
    assert root_story == (run.run_dir / "craft/variants/variant-1/story.md").read_text(encoding="utf-8")
    history = json.loads((run.run_dir / "craft_revision_history.json").read_text(encoding="utf-8"))
    assert len(history["attempts"]) == 2
    assert history["attempts"][0]["failed_blocking_ids"] == ["constraint:1"]
    assert history["attempts"][1]["passed"] is True

    planning_schemas = {
        "StoryPlanArtifact", "WorldArtifact", "CharactersArtifact", "StoryOutlineArtifact",
        "ChapterAnchorsArtifact", "PlotNodeProposal", "PlotNodeReview", "CraftVariantsArtifact",
        "CraftSelectionArtifact",
    }
    planning_calls = sum(name in planning_schemas for name, _, _ in provider.calls)
    alternate = generator.render_variant(run.run_dir, "variant-2")
    calls_after_render = sum(name in planning_schemas for name, _, _ in provider.calls)
    assert calls_after_render == planning_calls
    assert alternate.story_path.is_file()
    call_count = len(provider.calls)
    assert generator.render_variant(run.run_dir, "variant-2").story_path == alternate.story_path
    assert len(provider.calls) == call_count
    assert run.story_path.read_text(encoding="utf-8") == root_story
    assert (run.run_dir / "craft/selection.json").read_text(encoding="utf-8") == selection

    comparison = build_comparison(
        run.run_dir / "craft/variants/variant-1",
        run.run_dir / "craft/variants/variant-2",
        tmp_path / "comparison.html",
    )
    assert comparison.is_file()
    assert "Historia A" in comparison.read_text(encoding="utf-8")

    # The second chapter receives the complete immediately preceding chapter, not a multi-chapter tail.
    assert "PREVIOUS CHAPTER:\n## La señal" in provider.writer_prompts[1]
    # Active model-facing system instructions remain English while prose remains Spanish.
    systems = [system for _, system, _ in provider.calls]
    assert all("Eres " not in system and "Genera " not in system for system in systems)
    storyline_systems = [system.casefold() for name, system, _ in provider.calls
                         if name in {"StoryOutlineArtifact", "PlotNodeProposal", "PlotNodeReview"}]
    assert all(not any(term in system for term in ("promise", "payoff", "slider", "try-fail"))
               for system in storyline_systems)
    assert "llave roja" in root_story.casefold()


def test_render_variant_rejects_pre_v3_runs_actionably(tmp_path):
    run = tmp_path / "old-run"
    run.mkdir()
    with pytest.raises(ArtifactValidationError) as captured:
        StoryGenerator(V3Provider(), tmp_path, schema_repository=StaticRepository()).render_variant(
            run, "variant-2",
        )
    assert "Top-Down 3.0" in captured.value.summary
    assert captured.value.details["missing"]


class PlannerSequenceProvider:
    def __init__(self, reviews):
        self.reviews = iter(reviews)
        self.proposal_count = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is PlotNodeProposal:
            self.proposal_count += 1
            return PlotNodeProposal(
                subject=f"Rejected {self.proposal_count}", verb="tries", object="door",
                purpose="advance", schema_beat_id="beat-1", preconditions=["prior event"],
                effects=["state changes"], intention="open door", conflict="guard resists",
            )
        if schema is PlotNodeReview:
            return next(self.reviews)
        raise AssertionError(schema)


def single_chapter_inputs():
    story_outline = StoryOutlineArtifact(
        premise="p", synopsis="s", chapters=[ChapterPlan(
            id="chapter-001", order=1, title="One", abstract="a", target_words=350,
            freytag_phases=["exposition"],
        )],
    )
    anchors = ChapterAnchorsArtifact(anchors=[ChapterAnchors(
        chapter_id="chapter-001", begin_subject="Lía", begin_verb="finds", begin_object="key",
        end_subject="Lía", end_verb="opens", end_object="door",
    )])
    return story_outline, anchors


def accepted_review(**updates):
    payload = dict(
        accepted=True, causal=True, intentional=True, conflict_present=True, continuous=True,
        novel=True, advances_ending=True, world_consistent=True, aligns_with_cen=True,
        review_focus=["logic"],
    )
    payload.update(updates)
    return PlotNodeReview(**payload)


def test_incremental_planner_records_rejection_accepts_full_replacement_and_checkpoints():
    rejected = accepted_review(accepted=False, causal=False, aligns_with_cen=False,
                               issues=["No causal support"])
    replacement = PlotNodeProposal(
        subject="Lía", verb="unlocks", object="door", purpose="bridge to ending",
        schema_beat_id="beat-1", preconditions=["has key"], effects=["door unlocks"],
        intention="save district", conflict="guard resists",
        state_changes=[EntityStateChange(entity="Lía", attribute="knowledge", value="door is open")],
    )
    provider = PlannerSequenceProvider([rejected, accepted_review(revised=replacement)])
    planner = IncrementalPlotPlanner(provider, max_retries=1)
    checkpoints = []
    story_outline, anchors = single_chapter_inputs()
    storyline, history = planner.plan(
        story_outline, anchors, blueprint(),
        on_checkpoint=lambda story, graph, reviews: checkpoints.append(
            (len(story.nodes), len(graph.relations), len(reviews.rejected))
        ),
    )
    assert [node.node_type for node in storyline.nodes] == ["CBN", "CPN", "CEN"]
    assert storyline.nodes[1].subject == "Lía"
    assert all("Rejected" not in relation.source for relation in planner.nekg.artifact().relations)
    assert len(history.rejected) == 1
    assert len(checkpoints) == 4
    assert sum(node.target_words for node in storyline.nodes) == 350


def test_incremental_planner_enforces_adaptive_ceiling_and_cen_connection():
    story_outline, anchors = single_chapter_inputs()
    assert IncrementalPlotPlanner.max_cpn_count(story_outline.chapters[0]) == 1
    review = accepted_review(aligns_with_cen=False)
    planner = IncrementalPlotPlanner(PlannerSequenceProvider([review, review]), max_retries=1)
    with pytest.raises(StorylinePlanningError) as captured:
        planner.plan(story_outline, anchors, blueprint())
    assert captured.value.details["slot"] == 1
    assert captured.value.details["attempts"] == 2
