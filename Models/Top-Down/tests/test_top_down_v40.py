"""Top-Down 4.0 contract, dependency, craft, and architecture tests."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from asg_top_down.craft import (
    build_chapter_writing_brief, character_writing_cards,
    validate_character_arc_plan, validate_craft_alignment,
    validate_promise_ledger, validate_try_fail_plan,
)
from asg_top_down.schemas import (
    ChapterAnchors, ChapterAnchorsArtifact, ChapterCraftView, ChapterPlan,
    CharacterArcEvidence, CharacterArcPlan,
    CharacterProfile, CharacterSliderArc, CharactersArtifact, CraftAlignment,
    CraftAlignmentEntry, EntityRef, IncrementalStorylineArtifact, Location,
    NarrativeEdge, PlannedCharacterArc, PlotNode, PlotNodeProposal, PlotNodeReview,
    PromiseContract, PromiseLedger,
    PromiseOpening, PromisePayoff, PromiseProgress, SceneCraftDirective,
    SliderRange, StateMutation, StatePredicate, StoryCraftPlan, StoryObject,
    StoryFrame, StoryOutlineArtifact, StoryPlanArtifact, StoryRequest,
    TaxonomyApplication, TaxonomyOptionReference, ToneContract, TryFailCycle, TryFailPlan,
    WorldArtifact,
)
from asg_top_down.storyline.dependency import DependencyValidator
from asg_top_down.storyline.graph import NarrativeEntityGraph
from asg_top_down.storyline.planner import IncrementalPlotPlanner, StorylineState
from asg_top_down.generator import StoryGenerator
from asg_top_down.narrative_db import NarrativeSchemaRepository
from asg_top_down.schemas import CraftAuditArtifact, CraftComposition


def slider(arc_type="positive") -> CharacterSliderArc:
    if arc_type == "positive":
        values = dict(
            sympathy=SliderRange(start=3, target=8, rationale="Learns empathy"),
            competence=SliderRange(start=7, target=7, rationale="Already skilled"),
            proactivity=SliderRange(start=6, target=8, rationale="Acts decisively"),
            focus="sympathy",
        )
    elif arc_type == "negative":
        values = dict(
            sympathy=SliderRange(start=8, target=4, rationale="Rejects others"),
            competence=SliderRange(start=7, target=7, rationale="Remains capable"),
            proactivity=SliderRange(start=6, target=5, rationale="Still acts"),
            focus="sympathy",
        )
    else:
        values = dict(
            sympathy=SliderRange(start=7, target=7, rationale="Keeps compassion"),
            competence=SliderRange(start=7, target=8, rationale="Stays capable"),
            proactivity=SliderRange(start=5, target=5, rationale="Steady"),
            focus="sympathy", steadfast_truth="People deserve a choice",
            world_change="The town adopts consent as law",
        )
    return CharacterSliderArc(**values, arc_type=arc_type, justification="Observable behavior")


def profile(arc_type="positive") -> CharacterProfile:
    return CharacterProfile(
        id="mara", name="Mara", narrative_role="protagonist", ensemble_seat="leader",
        competence_domain="navigation", jungian_archetype="explorer", want="escape",
        need="trust the crew", misbelief="control prevents loss", wound="a failed rescue",
        strength="careful planning", flaw="withholds decisions", flaw_cost="the crew loses time",
        unspoken_rule="never improvise", voice="short precise sentences", notices="exits",
        goal="open the gate", motivation="save the town", conflict="the guard blocks her",
        arc="learns through choice", importance="main", initial_location_id="square",
        slider_arc=slider(arc_type),
    )


def world() -> WorldArtifact:
    return WorldArtifact(
        setting="A sealed town", time_period="near future", rules=["Doors need keys"],
        locations=[
            Location(id="square", name="Square", description="Central plaza",
                     connected_location_ids=["gate"]),
            Location(id="gate", name="Gate", description="Town exit",
                     connected_location_ids=["square"]),
            Location(id="tower", name="Tower", description="Remote tower"),
        ],
        objects=[StoryObject(id="key", name="Key", description="Opens the gate",
                             initial_location_id="square")],
        atmosphere="tense",
    )


def cast(arc_type="positive") -> CharactersArtifact:
    return CharactersArtifact(characters=[profile(arc_type)])


def chapters() -> StoryOutlineArtifact:
    return StoryOutlineArtifact(
        premise="Mara must leave", synopsis="She finds the key and opens the gate.",
        chapters=[
            ChapterPlan(id="c1", order=1, title="One", abstract="Search", target_words=400,
                        freytag_phases=["exposition"]),
            ChapterPlan(id="c2", order=2, title="Two", abstract="Test", target_words=400,
                        freytag_phases=["rising_action"]),
            ChapterPlan(id="c3", order=3, title="Three", abstract="Open", target_words=400,
                        freytag_phases=["climax"]),
        ],
    )


def ledger(two_primary_progress=True) -> PromiseLedger:
    promises = []
    for index, kind in enumerate(
        ("story_direction", "character_conflict", "genre_structure"), 1
    ):
        progress = [PromiseProgress(
            id=f"p{index}-g1", chapter_id="c2", mode="complicate",
            observable_delta="The route narrows", new_cost_or_information="the guard learns",
            reader_effect="greater uncertainty",
        )]
        if index == 1 and two_primary_progress:
            progress.append(PromiseProgress(
                id="p1-g2", chapter_id="c2", mode="reframe",
                observable_delta="The key serves another lock",
                new_cost_or_information="Mara must choose", reader_effect="surprise",
            ))
        promises.append(PromiseContract(
            id=f"p{index}", kind=kind, subject=f"subject {index}", expectation="an answer",
            dramatic_question="Will it work?", fulfillment_criteria=["visible consequence"],
            opening=PromiseOpening(id=f"p{index}-o", chapter_id="c1",
                                   signal="show the locked gate", reader_effect="anticipation"),
            progress=progress,
            payoff=PromisePayoff(
                id=f"p{index}-x", chapter_id="c3", answer="The gate opens at a cost",
                cost="Mara yields control", prepared_by_progress_ids=[item.id for item in progress],
                surprising_without_breach="The key opens trust before metal",
            ),
        ))
    return PromiseLedger(
        tone=ToneContract(description="tense hope", opening_signal="a failing light",
                          continuity_rule="hope always costs action", closing_echo="steady light"),
        primary_promise_id="p1", promises=promises,
    )


def arc_plan(arc_type="positive") -> CharacterArcPlan:
    return CharacterArcPlan(arcs=[PlannedCharacterArc(
        character_id="mara", arc_type=arc_type, focus_description="trust under pressure",
        enables_or_prevents_promise_id="p1",
        decisive_choice_uses_want="She can escape alone",
        decisive_choice_uses_need="She chooses to trust the crew",
        external_payoff_effect="enables",
        internal_to_external_rationale="Shared control lets the crew open the gate",
        evidences=[
            CharacterArcEvidence(id="a1", chapter_id="c1", stage="establishment",
                                 behavior="Mara excludes the crew", choice_or_cost="they lose time"),
            CharacterArcEvidence(id="a2", chapter_id="c2", stage="pressure",
                                 behavior="Her plan fails", choice_or_cost="the guard learns"),
            CharacterArcEvidence(id="a3", chapter_id="c3", stage="decisive_choice",
                                 behavior="She asks for help", choice_or_cost="shares control"),
            CharacterArcEvidence(id="a4", chapter_id="c3", stage="consequence",
                                 behavior="The crew opens the gate", choice_or_cost="all choose"),
        ],
    )])


def try_fail() -> TryFailPlan:
    return TryFailPlan(cycles=[
        TryFailCycle(id="t1", chapter_id="c2", promise_id="p1", action="use the old route",
                     outcome="no_and", consequence="the route seals", lesson="the map is watched",
                     stakes_change="the guard now pursues them"),
        TryFailCycle(id="t2", chapter_id="c2", promise_id="p2", action="deceive the guard",
                     outcome="yes_but", consequence="the guard waits at the gate",
                     lesson="the guard protects a child", stakes_change="force is now morally costly"),
    ])


def node(identifier, chapter, order, subject="mara", verb="acts", obj="key", deps=None):
    return PlotNode(
        id=identifier, chapter_id=chapter, node_type="CPN", location_id="square",
        subject=EntityRef(id=subject, name=subject, kind="character"), verb=verb,
        object=EntityRef(id=obj, name=obj, kind="object"), timestamp=order-1,
        global_order=order, local_order=order, target_words=100,
        goals=[{"purpose": "advance", "success_criteria": ["state changes"]}],
        depends_on_node_ids=deps or [], effects=[StateMutation(
            entity_id="mara", attribute="situation", value=f"after-{identifier}",
        )], intention="escape", conflict="guard", consequence="conditions change",
    )


def storyline() -> IncrementalStorylineArtifact:
    nodes = [
        node("n1", "c1", 1, verb="finds"),
        node("n2", "c2", 2, verb="tests", deps=["n1"]),
        node("n3", "c3", 3, verb="opens", deps=["n1", "n2"]),
    ]
    nodes[-1].node_type = "CEN"
    return IncrementalStorylineArtifact(
        chapters=chapters().chapters, nodes=nodes,
        accepted_edges=[
            NarrativeEdge(source="n1", target="n2", relation="causes", strength=5, rationale="x"),
            NarrativeEdge(source="n1", target="n3", relation="enables", strength=4, rationale="x"),
            NarrativeEdge(source="n2", target="n3", relation="causes", strength=5, rationale="x"),
        ], topological_order=["n1", "n2", "n3"],
    )


@pytest.mark.parametrize("arc_type", ["positive", "negative", "flat"])
def test_three_arc_types_validate(arc_type) -> None:
    assert slider(arc_type).arc_type == arc_type


def test_invalid_positive_and_flat_profiles_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CharacterSliderArc(
            sympathy=SliderRange(start=5, target=8, rationale="x"),
            competence=SliderRange(start=7, target=7, rationale="x"),
            proactivity=SliderRange(start=7, target=7, rationale="x"),
            focus="sympathy", arc_type="positive", justification="x",
        )
    with pytest.raises(ValidationError):
        CharacterSliderArc(
            sympathy=SliderRange(start=7, target=7, rationale="x"),
            competence=SliderRange(start=7, target=7, rationale="x"),
            proactivity=SliderRange(start=5, target=5, rationale="x"),
            focus="sympathy", arc_type="flat", justification="x",
        )


def test_storyline_projection_and_writing_cards_remove_slider_scaffolding() -> None:
    characters = cast()
    projection = characters.storyline_cast().model_dump_json()
    cards = character_writing_cards(characters)
    assert "slider" not in projection.casefold()
    assert "sympathy" not in projection.casefold()
    assert "slider" not in cards[0].model_dump_json().casefold()
    assert cards[0].flaw_pressure == "the crew loses time"


def test_ledger_order_primary_progress_and_arc_invariants() -> None:
    validate_promise_ledger(ledger(), chapters(), 1200)
    validate_character_arc_plan(arc_plan(), cast(), chapters(), ledger())
    bad = ledger(two_primary_progress=False)
    with pytest.raises(ValueError, match="two primary"):
        validate_promise_ledger(bad, chapters(), 1200)
    out_of_order = ledger().model_copy(deep=True)
    out_of_order.promises[0].opening.chapter_id = "c3"
    with pytest.raises(ValueError, match="open, progress"):
        validate_promise_ledger(out_of_order, chapters(), 1200)


def test_try_fail_and_alignment_reference_only_frozen_nodes() -> None:
    request = StoryRequest(
        original_prompt="x", processed_prompt="x", title="x", genre="drama", tone="tense",
        target_words=1200, premise="x",
    )
    validate_try_fail_plan(try_fail(), request, chapters(), ledger())
    arcs, cycles, story = arc_plan(), try_fail(), storyline()
    ids = {
        beat for promise in ledger().promises
        for beat in [promise.opening.id, *(x.id for x in promise.progress), promise.payoff.id]
    } | {item.id for arc in arcs.arcs for item in arc.evidences} | {x.id for x in cycles.cycles}
    chapter_for = {}
    for promise in ledger().promises:
        chapter_for[promise.opening.id] = "c1"
        chapter_for[promise.payoff.id] = "c3"
        chapter_for.update({item.id: item.chapter_id for item in promise.progress})
    chapter_for.update({item.id: item.chapter_id for arc in arcs.arcs for item in arc.evidences})
    chapter_for.update({item.id: item.chapter_id for item in cycles.cycles})
    node_for = {"c1": "n1", "c2": "n2", "c3": "n3"}
    alignment = CraftAlignment(entries=[CraftAlignmentEntry(
        craft_id=item, chapter_id=chapter_for[item], node_ids=[node_for[chapter_for[item]]],
    ) for item in sorted(ids)])
    views = [ChapterCraftView(
        chapter_id=chapter, opened_promise_ids=["p1"] if chapter == "c1" else [],
        progressed_promise_ids=["p1"] if chapter == "c2" else [],
        paid_promise_ids=["p1"] if chapter == "c3" else [],
        scene_directives=[SceneCraftDirective(
            node_id=node_for[chapter], goal="leave", conflict="guard",
            outcome="no_and" if chapter != "c3" else "final_resolution",
            consequence="cost", reaction="fear", dilemma="trust", decision="act",
        )],
    ) for chapter in ("c1", "c2", "c3")]
    validate_craft_alignment(
        alignment, views, ledger(), arcs, cycles, chapters(), story,
    )
    broken = alignment.model_copy(deep=True)
    broken.entries[0].node_ids = ["not-accepted"]
    with pytest.raises(ValueError, match="unaccepted"):
        validate_craft_alignment(broken, views, ledger(), arcs, cycles, chapters(), story)


def proposal(**updates):
    payload = dict(
        location_id="square", subject=EntityRef(id="mara", name="Mara", kind="character"),
        verb="uses", object=EntityRef(id="key", name="Key", kind="object"),
        purpose="open gate", depends_on_node_ids=[],
        effects=[StateMutation(entity_id="mara", attribute="situation", value="ready")],
        intention="escape", conflict="guard", consequence="the route changes",
    )
    payload.update(updates)
    from asg_top_down.schemas import PlotNodeProposal
    return PlotNodeProposal(**payload)


@pytest.mark.parametrize("candidate,code", [
    (proposal(location_id="tower", effects=[StateMutation(
        entity_id="mara", attribute="location", value="tower")]), "CHARACTER_ABSENT"),
    (proposal(object=EntityRef(id="ghost", name="Ghost", kind="object")), "UNKNOWN_ENTITY"),
    (proposal(preconditions=[StatePredicate(
        entity_id="mara", attribute="knowledge", value="secret")]), "FALSE_PRECONDITION"),
    (proposal(effects=[
        StateMutation(entity_id="mara", attribute="status", value="alive"),
        StateMutation(entity_id="mara", attribute="status", value="dead"),
    ]), "CONTRADICTORY_EFFECTS"),
])
def test_dependency_validator_rejects_invalid_world_changes(candidate, code) -> None:
    graph = NarrativeEntityGraph(world(), cast().storyline_cast())
    report = DependencyValidator(world(), cast().storyline_cast()).validate(
        candidate, graph.snapshot(), set(),
    )
    assert code in {item.code for item in report.issues}


def test_dead_character_and_rejected_candidate_do_not_mutate_graph() -> None:
    graph = NarrativeEntityGraph(world(), cast().storyline_cast())
    dead = graph.snapshot().model_copy(deep=True)
    next(item for item in dead.entities if item.id == "mara").state["status"] = "dead"
    report = DependencyValidator(world(), cast().storyline_cast()).validate(
        proposal(), dead, set(),
    )
    assert "DEAD_CHARACTER" in {item.code for item in report.issues}
    before = graph.snapshot()
    DependencyValidator(world(), cast().storyline_cast()).validate(proposal(), before, set())
    assert graph.snapshot() == before


def test_real_dag_supports_multiple_dependencies_and_adaptive_cpn_limits() -> None:
    outline = chapters()
    state = StorylineState(outline.chapters)
    first, second, third = storyline().nodes
    state.accept(first, [])
    state.accept(second, [NarrativeEdge(
        source="n1", target="n2", relation="causes", strength=5, rationale="x",
    )])
    state.accept(third, [
        NarrativeEdge(source="n1", target="n3", relation="enables", strength=4, rationale="x"),
        NarrativeEdge(source="n2", target="n3", relation="causes", strength=5, rationale="x"),
    ])
    assert state.artifact().topological_order == ["n1", "n2", "n3"]
    assert IncrementalPlotPlanner.min_cpn_count(outline.chapters[0]) == 2
    assert IncrementalPlotPlanner.max_cpn_count(outline.chapters[0]) == 3
    short = outline.chapters[0].model_copy(update={"target_words": 200})
    assert IncrementalPlotPlanner.min_cpn_count(short) == 1


def test_storyline_package_has_no_craft_dependency_or_forbidden_prompt_terms() -> None:
    root = Path(__file__).parents[1] / "src" / "asg_top_down" / "storyline"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    lowered = source.casefold()
    assert "craft_models" not in lowered
    assert "from ..craft" not in lowered
    assert "slider" not in lowered
    assert "try_fail" not in lowered
    assert "storylineobligation" not in lowered


class FullFakeProvider:
    model_name = "fake-v40"

    def __init__(self) -> None:
        self.calls = []
        self.proposal_index = 0
        self.review_index = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        self.calls.append((schema.__name__, system_instruction, prompt))
        if schema is StoryPlanArtifact:
            return StoryPlanArtifact(
                logline="Mara opens the sealed gate", theme="Trust permits freedom",
                central_conflict="Mara and the guard contest the gate",
                progression=["Mara finds the key", "She learns the route", "She trusts the crew"],
                intended_ending="The gate opens at a personal cost",
                story_frame=StoryFrame(
                    central_question="Can control create freedom?", a_plot_goal="Open the gate",
                    b_plot_need="Trust the crew", outer_mice_thread="event",
                    opening_state="The town is sealed", closing_state="The gate is open",
                    internal_change_enables_external_resolution="Shared control enables the escape",
                ),
                taxonomy_application=TaxonomyApplication(
                    primary_taxonomy_id="heist-caper",
                    selected_promises=[TaxonomyOptionReference(
                        taxonomy_id="heist-caper", option_id="promise-impossible-job")],
                    selected_movements=[
                        TaxonomyOptionReference(taxonomy_id="heist-caper", option_id="move-proposition"),
                        TaxonomyOptionReference(taxonomy_id="heist-caper", option_id="move-operation"),
                    ],
                    selected_conclusion=TaxonomyOptionReference(
                        taxonomy_id="heist-caper", option_id="end-costly-win"),
                    freshness_choices=["Trust is the decisive tool"], prompt_evidence=["heist"],
                    rationale="The operation is the factual engine",
                ),
            )
        if schema is WorldArtifact:
            return world().model_copy(update={"locations": world().locations[:2]})
        if schema is CharactersArtifact:
            return cast()
        if schema is StoryOutlineArtifact:
            return StoryOutlineArtifact(
                premise="Mara must open the gate", synopsis="She learns and acts.",
                chapters=[ChapterPlan(
                    id="c1", order=1, title="La puerta", abstract="Mara escapes",
                    target_words=600, freytag_phases=["exposition", "climax", "denouement"],
                )],
            )
        if schema is ChapterAnchorsArtifact:
            return ChapterAnchorsArtifact(anchors=[ChapterAnchors(
                chapter_id="c1", begin_location_id="square",
                begin_subject=EntityRef(id="mara", name="Mara", kind="character"),
                begin_verb="seeks", begin_object=EntityRef(id="key", name="Key", kind="object"),
                begin_effects=[StateMutation(entity_id="mara", attribute="situation", value="searching")],
                end_location_id="gate",
                end_subject=EntityRef(id="mara", name="Mara", kind="character"),
                end_verb="exits", end_object=EntityRef(id="gate", name="Gate", kind="location"),
                end_preconditions=[StatePredicate(entity_id="mara", attribute="location", value="gate")],
                end_effects=[StateMutation(entity_id="mara", attribute="situation", value="free")],
            )])
        if schema is PlotNodeProposal:
            self.proposal_index += 1
            if self.proposal_index == 1:
                return proposal(
                    verb="studies", depends_on_node_ids=["n_0001"],
                    effects=[StateMutation(entity_id="mara", attribute="knowledge", value="guard-route")],
                )
            return proposal(
                verb="carries", depends_on_node_ids=["n_0001", "n_0002"],
                effects=[StateMutation(entity_id="mara", attribute="location", value="gate")],
            )
        if schema is PlotNodeReview:
            self.review_index += 1
            return PlotNodeReview(
                accepted=True, causal=True, intentional=True, conflict_present=True,
                continuous=True, novel=True, advances_ending=True, world_consistent=True,
                emotionally_effective=True, aligns_with_cen=self.review_index == 2,
            )
        if schema is PromiseLedger:
            compact = ledger()
            for promise in compact.promises:
                promise.opening.chapter_id = "c1"
                promise.progress = [promise.progress[0].model_copy(update={"chapter_id": "c1"})]
                promise.payoff.chapter_id = "c1"
                promise.payoff.prepared_by_progress_ids = [promise.progress[0].id]
            return compact
        if schema is CharacterArcPlan:
            compact = arc_plan()
            for evidence in compact.arcs[0].evidences:
                evidence.chapter_id = "c1"
            return compact
        if schema is TryFailPlan:
            return TryFailPlan(cycles=[TryFailCycle(
                id="t1", chapter_id="c1", promise_id="p1", action="test the route",
                outcome="no_and", consequence="the guard notices", lesson="the route is watched",
                stakes_change="capture becomes immediate",
            )])
        if schema is CraftComposition:
            compact_ledger = self.generate_structured(
                system_instruction="fixture", prompt="fixture", schema=PromiseLedger,
            )
            compact_arcs = self.generate_structured(
                system_instruction="fixture", prompt="fixture", schema=CharacterArcPlan,
            )
            craft_ids = {
                beat for promise in compact_ledger.promises
                for beat in [promise.opening.id, *(x.id for x in promise.progress), promise.payoff.id]
            } | {x.id for arc in compact_arcs.arcs for x in arc.evidences} | {"t1"}
            return CraftComposition(
                alignment=CraftAlignment(entries=[CraftAlignmentEntry(
                    craft_id=item, chapter_id="c1", node_ids=["n_0002"],
                ) for item in sorted(craft_ids)]),
                chapters=[ChapterCraftView(
                    chapter_id="c1", opened_promise_ids=["p1", "p2", "p3"],
                    progressed_promise_ids=["p1", "p2", "p3"],
                    paid_promise_ids=["p1", "p2", "p3"],
                    scene_directives=[SceneCraftDirective(
                        node_id="n_0004", goal="leave", conflict="the guard",
                        outcome="final_resolution", consequence="freedom costs control",
                        reaction="relief", dilemma="alone or together", decision="trust",
                    )],
                )],
            )
        if schema is CraftAuditArtifact:
            return CraftAuditArtifact(answers=[], summary="fixture audit")
        raise AssertionError(schema)

    def generate_text(self, *, system_instruction, prompt):
        self.calls.append(("text", system_instruction, prompt))
        return " ".join(["palabra"] * 600)


def test_full_simulated_pipeline_freezes_storyline_before_craft(tmp_path) -> None:
    provider = FullFakeProvider()
    schemas = NarrativeSchemaRepository(db_path=tmp_path / "taxonomies.sqlite3")
    request = StoryRequest(
        original_prompt="Escribe un atraco de 600 palabras", processed_prompt="Write a 600-word heist",
        title="Prueba", language="Spanish", genre="heist", tone="tense",
        target_words=600, premise="Mara opens a gate",
    )
    run = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas,
        max_cpn_retries=0, max_artifact_retries=0, max_craft_revisions=0,
    ).generate(request)
    names = [item[0] for item in provider.calls]
    assert names.count("PlotNodeProposal") == 2
    assert max(index for index, name in enumerate(names) if name == "PlotNodeReview") < names.index("PromiseLedger")
    for name, system, prompt in provider.calls:
        if name in {"PlotNodeProposal", "PlotNodeReview"}:
            cpn_context = f"{system}\n{prompt}".casefold()
            assert not any(term in cpn_context for term in (
                "slider", "try_fail", "promiseledger", "storylineobligation", "ppp",
            ))
    assert (run.run_dir / "pipeline_manifest.json").is_file()
    assert (run.run_dir / "chapters" / "state-before-c1.json").is_file()
    brief = (run.run_dir / "craft" / "chapters" / "c1.brief.json").read_text(encoding="utf-8")
    assert '"state_before"' in brief and '"factual_events"' in brief
    assert "slider" not in brief.casefold()
    assert "searching" not in json.dumps(json.loads(brief)["state_before"])
    assert (run.run_dir / "story.md").is_file()
