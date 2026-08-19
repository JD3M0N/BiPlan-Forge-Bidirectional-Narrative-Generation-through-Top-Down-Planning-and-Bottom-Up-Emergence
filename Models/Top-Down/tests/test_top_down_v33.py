"""Regression coverage for the modular Top-Down 3.3 pipeline."""

import json

import pytest
from pydantic import ValidationError

from asg_top_down.agents import AnalystAgent
from asg_top_down.craft import (
    audit_questions, build_chapter_writing_brief, build_storyline_obligations,
    validate_chapter_ppp, validate_character_arc_plan, validate_global_ppp,
    validate_try_fail_plan,
)
from asg_top_down.errors import ArtifactValidationError, StorylinePlanningError
from asg_top_down.generator import StoryGenerator
from asg_top_down.incremental import IncrementalPlotPlanner
from asg_top_down.narrative_db import (
    CatalogEntry, NarrativeBlueprint, NarrativeSchemaRepository, RetrievalTrace,
)
from asg_top_down.nekg import NarrativeEntityGraph
from asg_top_down.schemas import (
    ChapterAnchors, ChapterAnchorsArtifact, ChapterPPPBeat, ChapterPPPPlan, ChapterPlan,
    Character, CharacterArcPlan, CharacterMilestone, CharactersArtifact, CharacterSliderArc,
    CraftAuditAnswer, CraftAuditArtifact, EntityStateChange, GlobalPPPLine,
    GlobalPPPPlan, GlobalPPPPoint, PlotNode, PlotNodeProposal, PlotNodeReview,
    SliderRange, StoryCraftPlan, StoryOutlineArtifact, StoryPlanArtifact, StoryRequest,
    TonePromise, TryFailCycle, TryFailPlan, WorldArtifact,
)


def blueprint() -> NarrativeBlueprint:
    entries = {
        kind: [CatalogEntry(
            id=f"{kind}-1", kind=kind, name=kind, description=f"{kind} description",
            provenance="test",
        )]
        for kind in ("macroplot", "situation", "character_arc", "beat", "genre", "role")
    }
    return NarrativeBlueprint(
        macroplots=entries["macroplot"], situations=entries["situation"],
        character_arcs=entries["character_arc"], beats=entries["beat"],
        genres=entries["genre"], roles=entries["role"],
        trace=RetrievalTrace(query="test", selections=entries),
    )


class StaticRepository:
    def retrieve(self, _request):
        return blueprint()


def request() -> StoryRequest:
    return StoryRequest(
        original_prompt="Escribe en español y conserva una llave roja.",
        processed_prompt="Write a tense fantasy story about a red key and a sealed door.",
        title="The Key", language="Spanish", genre="fantasy", tone="tense",
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
            ChapterPlan(id="chapter-001", order=1, title="La señal",
                        abstract="Encuentra la llave", target_words=350,
                        freytag_phases=["exposition", "rising_action"]),
            ChapterPlan(id="chapter-002", order=2, title="La puerta",
                        abstract="Decide abrirla", target_words=350,
                        freytag_phases=["climax", "denouement"]),
        ],
    )


def global_ppp() -> GlobalPPPPlan:
    return GlobalPPPPlan(
        tone_promise=TonePromise(
            description="Tense hope", opening_signal="A guarded key",
            continuity_rule="Hope grows through costly choices",
        ),
        primary_line=GlobalPPPLine(
            id="door", kind="plot", subject="The promised door",
            promise=GlobalPPPPoint(
                id="door-promise", chapter_id="chapter-001",
                description="The door may save the district", reader_effect="Expect salvation",
            ),
            progress=[GlobalPPPPoint(
                id="door-progress", chapter_id="chapter-001",
                description="The key reveals its price", reader_effect="Feel costly progress",
            )],
            payoff=GlobalPPPPoint(
                id="door-payoff", chapter_id="chapter-002",
                description="Lía opens the door at a price", reader_effect="Receive earned hope",
            ),
        ),
    )


def character_arc_plan() -> CharacterArcPlan:
    return CharacterArcPlan(milestones=[
        CharacterMilestone(character_name="Lía", chapter_id="chapter-001", stage="start",
                           description="She waits for another person to act"),
        CharacterMilestone(character_name="Lía", chapter_id="chapter-001", stage="transition",
                           description="She tests the mechanism herself"),
        CharacterMilestone(character_name="Lía", chapter_id="chapter-002", stage="end",
                           description="She opens the door by her own decision"),
    ])


def try_fail_plan() -> TryFailPlan:
    return TryFailPlan(cycles=[
        TryFailCycle(id="try-1", chapter_id="chapter-001", action="Test the key",
                     outcome="yes_but", consequence="The guardian locates her"),
        TryFailCycle(id="try-2", chapter_id="chapter-002", action="Turn the mechanism",
                     outcome="no_and", consequence="She loses time and must commit"),
    ])


def local_ppp(chapter_id: str, invalid: bool = False) -> ChapterPPPPlan:
    if chapter_id == "chapter-001":
        ids = ["foreign", "n_0002", "n_0003"] if invalid else ["n_0001", "n_0002", "n_0003"]
        advances = ["door-promise", "door-progress"]
    else:
        ids = ["n_0004", "n_0005", "n_0006"]
        advances = ["door-payoff"]
    return ChapterPPPPlan(
        chapter_id=chapter_id,
        promise=ChapterPPPBeat(description="A local expectation is established", node_ids=[ids[0]]),
        progress=[ChapterPPPBeat(description="Conflict signals progress", node_ids=[ids[1]])],
        payoff=ChapterPPPBeat(description="The expectation changes consequentially", node_ids=[ids[2]]),
        advances_global_point_ids=advances,
    )


class V33Provider:
    model_name = "fake-v33"

    def __init__(self, fail_first_audit=False, invalid_local_calls=0):
        self.usage_records = []
        self.usage_callback = None
        self.wait_callback = None
        self.calls = []
        self.writer_prompts = []
        self.audit_calls = 0
        self.fail_first_audit = fail_first_audit
        self.invalid_local_calls = invalid_local_calls

    def generate_structured(self, *, system_instruction, prompt, schema):
        self.calls.append((schema.__name__, system_instruction, prompt))
        if schema is StoryPlanArtifact:
            return StoryPlanArtifact(
                logline="Lía must open a door", theme="Choice creates hope",
                central_conflict="Lía against the guardian",
                progression=["find", "test", "decide"], intended_ending="The door opens",
                archetypes={"primary": "macroplot-1", "secondary": ["situation-1"],
                            "confidence": .9, "rationale": "causal"},
            )
        if schema is WorldArtifact:
            return WorldArtifact(setting="Walled district", time_period="night",
                                 rules=["The key cannot be copied"], locations=["door"],
                                 atmosphere="tense")
        if schema is CharactersArtifact:
            return characters()
        if schema is StoryOutlineArtifact:
            return outline()
        if schema is GlobalPPPPlan:
            return global_ppp()
        if schema is CharacterArcPlan:
            return character_arc_plan()
        if schema is TryFailPlan:
            return try_fail_plan()
        if schema is ChapterAnchorsArtifact:
            return ChapterAnchorsArtifact(anchors=[
                ChapterAnchors(chapter_id="chapter-001", begin_subject="Lía", begin_verb="finds",
                               begin_object="the key", end_subject="the door", end_verb="responds",
                               end_object="to Lía"),
                ChapterAnchors(chapter_id="chapter-002", begin_subject="Lía", begin_verb="enters",
                               begin_object="the threshold", end_subject="Lía", end_verb="opens",
                               end_object="the door"),
            ])
        if schema is PlotNodeProposal:
            second = '"title": "La puerta"' in prompt
            return PlotNodeProposal(
                subject="Lía", verb="decides" if second else "tests", object="the mechanism",
                purpose="Advance toward the door", schema_beat_id="beat-1",
                preconditions=["Lía keeps the key"], effects=["The mechanism changes"],
                intention="Open the door", conflict="The guardian interferes",
                state_changes=[EntityStateChange(entity="Lía", attribute="knowledge",
                                                 value="knows the price")],
            )
        if schema is PlotNodeReview:
            return PlotNodeReview(
                accepted=True, causal=True, intentional=True, conflict_present=True,
                continuous=True, novel=True, advances_ending=True, world_consistent=True,
                aligns_with_cen=True, review_focus=["logic"],
            )
        if schema is ChapterPPPPlan:
            second = '"title": "La puerta"' in prompt
            invalid = not second and self.invalid_local_calls > 0
            if invalid:
                self.invalid_local_calls -= 1
            return local_ppp("chapter-002" if second else "chapter-001", invalid=invalid)
        if schema is CraftAuditArtifact:
            self.audit_calls += 1
            document = json.loads(prompt.split("QUESTIONS:\n", 1)[1].split("\n\nFICTION:", 1)[0])
            answers = []
            for question in document:
                fail = (self.fail_first_audit and self.audit_calls == 1
                        and question["question_id"] == "constraint:1")
                answers.append(CraftAuditAnswer(
                    **question, verdict="fail" if fail else "pass",
                    evidence="Visible in the fiction", issue="The key breaks" if fail else "",
                    revision_instruction="Keep the key intact" if fail else "",
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
    with pytest.raises(ValidationError):
        CharacterSliderArc(
            sympathy=SliderRange(start=8, target=9, rationale="x"),
            competence=SliderRange(start=6, target=8, rationale="x"),
            proactivity=SliderRange(start=2, target=8, rationale="x"),
            focus="proactivity", justification="x",
        )


@pytest.mark.parametrize(("prompt", "language"), [
    ("Escribe una historia sobre un faro.", "Spanish"),
    ("Write a story about a lighthouse.", "English"),
    ("Escribe una historia sobre un faro, pero en inglés.", "English"),
])
def test_analyst_preserves_prompt_and_language(prompt, language):
    class AnalystProvider:
        def generate_structured(self, *, system_instruction, prompt, schema):
            return StoryRequest(
                original_prompt="changed", processed_prompt="Write a complete lighthouse mystery.",
                title="Lighthouse", language=language, genre="mystery", tone="tense",
                premise="A keeper must choose.", constraints=[],
            )
    result = AnalystAgent(AnalystProvider(), default_target_words=900).run(prompt)
    assert result.original_prompt == prompt
    assert result.language == language
    assert result.target_words == 900


def test_storyteller_node_contracts_contain_no_craft_fields():
    forbidden = {"promise", "progress", "payoff", "slider", "try_fail", "yes_but", "no_and"}
    for schema in (ChapterPlan, PlotNode, PlotNodeProposal, PlotNodeReview):
        names = {name.casefold() for name in schema.model_fields}
        assert not any(any(term in name for term in forbidden) for name in names)


def test_modular_contracts_validate_and_writer_brief_strips_internal_ids():
    validate_global_ppp(global_ppp(), outline())
    validate_character_arc_plan(character_arc_plan(), outline(), characters())
    validate_try_fail_plan(try_fail_plan(), outline(), request().target_words)
    obligations = build_storyline_obligations(global_ppp(), character_arc_plan(), try_fail_plan())
    assert {item.source for item in obligations.obligations} == {
        "global_ppp", "character_arc", "try_fail",
    }
    brief = build_chapter_writing_brief(
        global_ppp(), local_ppp("chapter-001"), character_arc_plan(), try_fail_plan(),
    )
    serialized = json.dumps(brief.model_dump(mode="json"))
    assert "n_0001" not in serialized
    assert "door-promise" not in serialized


def test_chapter_ppp_rejects_foreign_nodes_and_audit_is_blocking():
    provider = V33Provider()
    generator = StoryGenerator(provider, ".", schema_repository=StaticRepository())
    # Build a real accepted storyline without writing a run.
    planner = IncrementalPlotPlanner(provider, max_retries=0)
    obligations = build_storyline_obligations(global_ppp(), character_arc_plan(), try_fail_plan())
    anchors = provider.generate_structured(system_instruction="", prompt="", schema=ChapterAnchorsArtifact)
    storyline, _ = planner.plan(outline(), anchors, blueprint(), obligations)
    with pytest.raises(ValueError, match="unknown or foreign"):
        validate_chapter_ppp(local_ppp("chapter-001", invalid=True), outline().chapters[0],
                             storyline, global_ppp())
    craft = StoryCraftPlan(global_ppp=global_ppp(), character_arcs=character_arc_plan(),
                           try_fail=try_fail_plan(), chapters=[
                               local_ppp("chapter-001"), local_ppp("chapter-002"),
                           ])
    questions = audit_questions(request(), craft, characters())
    assert next(item for item in questions if item["question_id"] == "global_ppp:door:earned")["blocking"]
    assert next(item for item in questions if item["question_id"] == "constraint:1")["blocking"]


def test_generator_persists_modular_craft_rewrites_and_sanitizes_writer(tmp_path):
    provider = V33Provider(fail_first_audit=True)
    run = StoryGenerator(
        provider, tmp_path, schema_repository=StaticRepository(),
        max_cpn_retries=0, max_craft_revisions=2,
    ).generate(request())
    assert run.story_path.is_file()
    for relative in (
        "craft/global_ppp.json", "craft/character_arcs.json", "craft/try_fail.json",
        "craft/chapters/chapter-001.ppp.json", "craft/chapters/chapter-001.brief.json",
        "storyline_obligations.json", "storyline_obligation_trace.json",
    ):
        assert (run.run_dir / relative).is_file()
    assert not (run.run_dir / "craft/variants").exists()
    assert not hasattr(StoryGenerator, "render_variant")
    assert [name for name, _, _ in provider.calls].count("GlobalPPPPlan") == 1
    assert [name for name, _, _ in provider.calls].count("ChapterPPPPlan") == 2
    assert len(provider.writer_prompts) == 2
    assert all("CHAPTER WRITING BRIEF:" in prompt for prompt in provider.writer_prompts)
    assert all("n_000" not in prompt and "CBN" not in prompt and "CPN" not in prompt
               for prompt in provider.writer_prompts)
    history = json.loads((run.run_dir / "craft_revision_history.json").read_text(encoding="utf-8"))
    assert len(history["attempts"]) == 2
    assert "llave roja" in run.story_path.read_text(encoding="utf-8").casefold()


def test_missing_local_coverage_replans_storyline_once(tmp_path):
    provider = V33Provider(invalid_local_calls=1)
    run = StoryGenerator(
        provider, tmp_path, schema_repository=StaticRepository(), max_cpn_retries=0,
        max_artifact_retries=0, max_craft_revisions=0,
    ).generate(request())
    names = [name for name, _, _ in provider.calls]
    assert names.count("ChapterAnchorsArtifact") == 2
    assert names.count("ChapterPPPPlan") == 3
    assert (run.run_dir / "storyline_replans/attempt-1/coverage_failure.json").is_file()
    assert (run.run_dir / "storyline_replans/attempt-2/storyline.json").is_file()


def test_missing_local_coverage_fails_after_exactly_one_replan(tmp_path):
    provider = V33Provider(invalid_local_calls=10)
    with pytest.raises(ArtifactValidationError, match="replanificación estructural") as captured:
        StoryGenerator(
            provider, tmp_path, schema_repository=StaticRepository(), max_cpn_retries=0,
            max_artifact_retries=0, max_craft_revisions=0,
        ).generate(request())
    assert captured.value.details["structural_attempts"] == 2
    assert [name for name, _, _ in provider.calls].count("ChapterAnchorsArtifact") == 2


def test_nekg_prioritizes_directed_pair_then_recent_incident_relations():
    graph = NarrativeEntityGraph()
    def node(identifier, subject, object_, timestamp):
        return PlotNode(
            id=identifier, chapter_id="chapter-001", node_type="CPN", subject=subject,
            verb="sees", object=object_, timestamp=timestamp, global_order=timestamp + 1,
            local_order=timestamp + 1, target_words=10,
            goals=[{"purpose": "x", "archetype_id": "x", "schema_beat_id": "x",
                    "success_criteria": ["x"]}],
        )
    graph.apply(node("n_0001", "Lía", "Door", 1))
    graph.apply(node("n_0002", "Door", "Lía", 9))
    graph.apply(node("n_0003", "Lía", "Guardian", 8))
    assert [item.plot_node_id for item in graph.related("Lía", "Door", limit=10)] == [
        "n_0001", "n_0002", "n_0003",
    ]


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


def test_incremental_planner_records_rejection_and_accepts_replacement():
    rejected = accepted_review(accepted=False, causal=False, aligns_with_cen=False,
                               issues=["No causal support"])
    replacement = PlotNodeProposal(
        subject="Lía", verb="unlocks", object="door", purpose="bridge to ending",
        schema_beat_id="beat-1", preconditions=["has key"], effects=["door unlocks"],
        intention="save district", conflict="guard resists",
        state_changes=[EntityStateChange(entity="Lía", attribute="knowledge", value="open")],
    )
    planner = IncrementalPlotPlanner(
        PlannerSequenceProvider([rejected, accepted_review(revised=replacement)]), max_retries=1,
    )
    checkpoints = []
    story_outline, anchors = single_chapter_inputs()
    storyline, history = planner.plan(
        story_outline, anchors, blueprint(),
        on_checkpoint=lambda story, graph, reviews: checkpoints.append(len(story.nodes)),
    )
    assert [node.node_type for node in storyline.nodes] == ["CBN", "CPN", "CEN"]
    assert storyline.nodes[1].subject == "Lía"
    assert len(history.rejected) == 1
    assert len(checkpoints) == 4


def test_incremental_planner_enforces_adaptive_ceiling():
    story_outline, anchors = single_chapter_inputs()
    review = accepted_review(aligns_with_cen=False)
    planner = IncrementalPlotPlanner(PlannerSequenceProvider([review, review]), max_retries=1)
    with pytest.raises(StorylinePlanningError):
        planner.plan(story_outline, anchors, blueprint())


class V31Provider(V33Provider):
    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is StoryPlanArtifact:
            self.calls.append((schema.__name__, system_instruction, prompt))
            return StoryPlanArtifact(
                logline="Lía leads a crew into an impossible vault",
                theme="Trust makes expertise meaningful",
                central_conflict="The crew against a guarded institution",
                progression=["recruit", "reconnoiter", "adapt", "escape"],
                intended_ending="The crew escapes after choosing trust",
                taxonomy_application={
                    "primary_taxonomy_id": "heist-caper",
                    "selected_promises": [{"taxonomy_id": "heist-caper",
                                           "option_id": "promise-impossible-job"}],
                    "selected_roles": [],
                    "selected_movements": [
                        {"taxonomy_id": "heist-caper", "option_id": "move-proposition"},
                        {"taxonomy_id": "heist-caper", "option_id": "move-operation"},
                    ],
                    "selected_complications": [],
                    "selected_conclusion": {"taxonomy_id": "heist-caper",
                                            "option_id": "end-costly-win"},
                    "freshness_choices": ["Let empathy defeat security."],
                    "prompt_evidence": ["The request asks for a heist."],
                    "rationale": "The operation is central.",
                },
            )
        return super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema,
        )


def test_v31_taxonomy_brief_reaches_modular_agents_and_writer(tmp_path):
    provider = V31Provider()
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    run = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=repository,
        max_cpn_retries=0, max_craft_revisions=0,
    ).generate(request().model_copy(update={
        "original_prompt": "Escribe un atraco con una llave roja.",
        "genre": "atraco", "premise": "Lía dirige un equipo hacia una bóveda.",
    }))
    assert (run.run_dir / "taxonomy_brief.json").is_file()
    global_prompt = next(prompt for name, _, prompt in provider.calls if name == "GlobalPPPPlan")
    assert "TAXONOMY BRIEF:" in global_prompt
    assert all("TAXONOMY BRIEF:" in prompt for prompt in provider.writer_prompts)
