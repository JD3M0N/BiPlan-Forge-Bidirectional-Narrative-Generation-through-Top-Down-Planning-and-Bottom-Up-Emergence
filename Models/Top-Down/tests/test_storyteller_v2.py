import json

import pytest

from asg_top_down.generator import StoryGenerator
from asg_top_down.compare import build_comparison
from asg_top_down.errors import StorylinePlanningError, StructuredResponseError
from asg_top_down.incremental import IncrementalPlotPlanner
from asg_top_down.narrative_db import NarrativeSchemaRepository
from asg_top_down.schemas import (
    ArchetypeSelection, ChapterAnchors, ChapterAnchorsArtifact, ChapterPlan,
    Character, CharacterMilestone, CharacterSliderArc, CharactersArtifact,
    CraftAuditAnswer, CraftAuditArtifact, CraftBeat, CraftContractArtifact,
    CraftPromise, PlotNodeProposal, PlotNodeReview, SliderRange,
    StoryOutlineArtifact, StoryPlanArtifact, StoryRequest, TryFailCycle,
    WorldArtifact,
)


class V2Provider:
    model_name = "fake"
    embedding_model_name = "fake-embedding"

    def __init__(self):
        self.document_batches = 0
        self.query_calls = 0
        self.proposals = 0

    def embed_documents(self, texts):
        self.document_batches += 1
        return [[float("misterio" in text.casefold()), 1.0] for text in texts]

    def embed_query(self, text):
        self.query_calls += 1
        return [1.0, 1.0]

    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is StoryPlanArtifact:
            return StoryPlanArtifact(logline="Ada descubre la verdad", theme="verdad",
                central_conflict="Ada contra el encubrimiento", progression=["indicio", "coste", "revelación"],
                intended_ending="Ada revela la señal", archetypes=ArchetypeSelection(
                    primary="mystery", confidence=.8, rationale="La verdad está oculta"))
        if schema is WorldArtifact:
            return WorldArtifact(setting="estación", time_period="futuro", rules=["mensajes bloqueados"],
                                 locations=["archivo"], atmosphere="tensa")
        if schema is CharactersArtifact:
            return CharactersArtifact(characters=[Character(name="Ada", narrative_role="protagonist",
                jungian_archetype="protagonist", goal="revelar", motivation="proteger", conflict="censura",
                arc="decide actuar", importance="main", slider_arc=CharacterSliderArc(
                    sympathy=SliderRange(start=8, target=8, rationale="El lector comprende su riesgo"),
                    competence=SliderRange(start=7, target=7, rationale="Ya sabe investigar"),
                    proactivity=SliderRange(start=3, target=8, rationale="Pasa de observar a actuar"),
                    focus="proactivity", direction="ascending",
                    justification="Sus decisiones revelan la señal"))])
        if schema is CraftContractArtifact:
            return CraftContractArtifact(try_fail_target=2, promises=[
                CraftPromise(id="tone", kind="tone", statement="Tensión", setup="Amenaza",
                             progress_signals=["Aumenta el peligro"], payoff="Alivio tenso"),
                CraftPromise(id="plot", kind="plot", statement="Revelar la señal",
                             setup="Ada encuentra la señal", progress_signals=["Ada la descifra"],
                             payoff="Ada la revela"),
                CraftPromise(id="ada", kind="character", character_name="Ada",
                             statement="Ada actuará", setup="Ada duda",
                             progress_signals=["Ada se arriesga"], payoff="Ada decide actuar"),
            ])
        if schema is StoryOutlineArtifact:
            return StoryOutlineArtifact(premise="Una señal censurada", synopsis="Ada encuentra y revela la señal",
                chapters=[ChapterPlan(id="ch1", order=1, title="Señal", abstract="Ada investiga",
                    target_words=450, freytag_phases=["exposition", "climax", "denouement"],
                    craft_beats=[
                        CraftBeat(id=f"{promise}-{kind}", promise_id=promise, kind=kind,
                                  description=f"{kind} {promise}")
                        for promise in ("tone", "plot", "ada")
                        for kind in ("setup", "progress", "payoff")
                    ],
                    character_milestones=[
                        CharacterMilestone(id=f"ada-{stage}", character_name="Ada", stage=stage,
                            focus_slider="proactivity", demonstrated_value=value,
                            description=f"Ada {stage}")
                        for stage, value in (("start", 3), ("transition", 5), ("end", 8))
                    ],
                    try_fail_cycles=[
                        TryFailCycle(id="tf1", action="Ada copia la señal", outcome="yes_but",
                                     consequence="La censura detecta la copia", promise_id="plot"),
                        TryFailCycle(id="tf2", action="Ada intenta transmitir", outcome="no_and",
                                     consequence="La censura bloquea a Ada", promise_id="plot"),
                    ])])
        if schema is ChapterAnchorsArtifact:
            return ChapterAnchorsArtifact(anchors=[ChapterAnchors(chapter_id="ch1",
                begin_subject="Ada", begin_verb="encuentra", begin_object="una señal",
                end_subject="Ada", end_verb="revela", end_object="la señal")])
        if schema is PlotNodeProposal:
            self.proposals += 1
            first = self.proposals % 2 == 1
            return PlotNodeProposal(subject="Ada", verb="descifra", object="la señal", purpose="descubrir el encubrimiento",
                schema_beat_id="escalation", preconditions=["Ada posee la señal"], effects=["Ada conoce la verdad"],
                intention="proteger a la tripulación", conflict="la censura detecta su acceso",
                state_changes=[{"entity":"Ada", "attribute":"knowledge", "value":"verdad de la señal"}],
                craft_beat_ids=(["tone-progress", "plot-progress", "ada-progress"] if first else []),
                character_milestone_ids=(["ada-transition"] if first else []),
                try_fail_cycle_ids=(["tf1"] if first else ["tf2"]),
                try_fail_outcome=("yes_but" if first else "no_and"))
        if schema is PlotNodeReview:
            return PlotNodeReview(accepted=True, causal=True, intentional=True, conflict_present=True,
                continuous=True, novel=True, advances_ending=True, world_consistent=True)
        if schema is CraftAuditArtifact:
            questions = json.loads(prompt.split("QUESTIONS:\n", 1)[1].split("\n\nFICTION:\n", 1)[0])
            return CraftAuditArtifact(summary="Cumple", answers=[
                CraftAuditAnswer(**question, verdict="pass", evidence="Visible en la historia")
                for question in questions
            ])
        raise AssertionError(schema)

    def generate_text(self, **kwargs):
        return "Ada descifró la señal porque necesitaba proteger a la tripulación. La censura respondió."


class RevisionProvider(V2Provider):
    def __init__(self, failed_audits: int, *, fail_rewriter: bool = False):
        super().__init__()
        self.failed_audits = failed_audits
        self.fail_rewriter = fail_rewriter
        self.audit_calls = 0
        self.rewrite_calls = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is CraftAuditArtifact:
            self.audit_calls += 1
            questions = json.loads(prompt.split("QUESTIONS:\n", 1)[1].split("\n\nFICTION:\n", 1)[0])
            fail = self.audit_calls <= self.failed_audits
            answers = []
            for index, question in enumerate(questions):
                if fail and index == 0:
                    answers.append(CraftAuditAnswer(
                        **question, verdict="fail", evidence="La promesa no aparece",
                        issue="Falta el planteamiento", revision_instruction="Plantea la promesa al abrir",
                    ))
                else:
                    answers.append(CraftAuditAnswer(
                        **question, verdict="pass", evidence="Visible en la historia",
                    ))
            return CraftAuditArtifact(summary="Revisión simulada", answers=answers)
        return super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema,
        )

    def generate_text(self, *, system_instruction, prompt):
        if "literary rewriter" in system_instruction:
            self.rewrite_calls += 1
            if self.fail_rewriter:
                raise RuntimeError("fallo simulado del reescritor")
            return f"Revisión completa {self.rewrite_calls}."
        return super().generate_text(system_instruction=system_instruction, prompt=prompt)


class InvalidNodeReviewProvider(V2Provider):
    def __init__(self, invalid_reviews: int):
        super().__init__()
        self.invalid_reviews = invalid_reviews
        self.review_calls = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is PlotNodeReview:
            self.review_calls += 1
            if self.review_calls <= self.invalid_reviews:
                raise StructuredResponseError(
                    "respuesta inválida simulada",
                    details={
                        "schema": "PlotNodeReview", "attempts": 2,
                        "validation_errors": [{"location": "$", "type": "model_validator"}],
                    },
                )
        return super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema,
        )


def test_schema_database_is_reproducible_and_embedding_cache_is_reused(tmp_path):
    provider = V2Provider()
    repository = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="misterio de una señal", title="Señal", genre="detective",
                           tone="tenso", premise="Una señal oculta la verdad")
    first = repository.retrieve(request)
    second = repository.retrieve(request)
    assert len(repository.entries()) == 22
    assert first.macroplots[0].id == "mystery"
    assert second.trace.used_embeddings
    assert provider.document_batches == 1
    assert provider.query_calls == 2


def test_retrieval_falls_back_to_fts_when_embeddings_are_offline(tmp_path):
    provider = V2Provider()
    provider.embed_documents = lambda texts: (_ for _ in ()).throw(ConnectionError("offline"))
    repository = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="detective investiga pistas y un secreto", title="x",
                           genre="detective", tone="oscuro", premise="resolver un misterio")
    blueprint = repository.retrieve(request)
    assert blueprint.trace.used_embeddings is False
    assert blueprint.macroplots[0].id == "mystery"


def test_incremental_generator_updates_nekg_and_writes_new_artifacts(tmp_path):
    provider = V2Provider()
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="misterio de una señal", title="Señal", genre="detective",
                           tone="tenso", premise="Una señal oculta la verdad", target_words=450)
    result = StoryGenerator(provider, tmp_path / "stories", schema_repository=schemas).generate(request)
    names = {path.name for path in result.run_dir.iterdir()}
    assert {"blueprint.json", "retrieval_trace.json", "outline.json", "chapter_anchors.json",
            "storyline.json", "nekg.json", "node_reviews.json", "craft_contract.json",
            "draft.md", "craft_audit.json", "craft_revision_history.json",
            "diagnostic_audit.json", "story.md"} <= names
    assert (result.run_dir / "planning_checkpoint" / "storyline.json").is_file()
    graph = json.loads((result.run_dir / "storyline.json").read_text(encoding="utf-8"))
    assert [node["node_type"] for node in graph["nodes"]] == ["CBN", "CPN", "CPN", "CEN"]
    assert len(graph["accepted_edges"]) == 3
    cycle_nodes = [node for node in graph["nodes"] if node["try_fail_cycle_ids"]]
    assert [node["try_fail_outcome"] for node in cycle_nodes] == ["yes_but", "no_and"]
    assert "La censura detecta la copia" in cycle_nodes[0]["effects"]
    assert "La censura bloquea a Ada" in cycle_nodes[1]["effects"]
    assert {node["id"] for node in cycle_nodes} <= {
        edge["source"] for edge in graph["accepted_edges"]
    }
    nekg = json.loads((result.run_dir / "nekg.json").read_text(encoding="utf-8"))
    ada = next(entity for entity in nekg["entities"] if entity["name"] == "Ada")
    assert ada["state"]["knowledge"] == "verdad de la señal"


def test_cpn_budget_prefers_fewer_developed_events():
    chapter = ChapterPlan(id="ch", order=1, title="x", abstract="x", target_words=1500,
                          freytag_phases=["rising_action"])
    assert IncrementalPlotPlanner.cpn_budget(chapter) == 4


@pytest.mark.parametrize(
    ("failed_audits", "expected_rewrites", "selected", "exhausted"),
    [(0, 0, 0, False), (1, 1, 1, False), (2, 2, 2, False), (99, 2, 2, True)],
)
def test_craft_revision_loop_selects_the_best_version(
    tmp_path, failed_audits, expected_rewrites, selected, exhausted,
):
    provider = RevisionProvider(failed_audits)
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="misterio", title="Señal", genre="detective",
                           tone="tenso", premise="Una señal oculta la verdad", target_words=450)
    result = StoryGenerator(provider, tmp_path / "stories", schema_repository=schemas).generate(request)
    history = json.loads((result.run_dir / "craft_revision_history.json").read_text(encoding="utf-8"))
    audit = json.loads((result.run_dir / "craft_audit.json").read_text(encoding="utf-8"))
    assert provider.rewrite_calls == expected_rewrites
    assert history["selected_attempt"] == selected
    assert history["exhausted"] is exhausted
    assert audit["passed"] is (not exhausted)
    assert len(history["attempts"]) == expected_rewrites + 1


def test_rewriter_failure_preserves_draft_and_audit(tmp_path):
    provider = RevisionProvider(99, fail_rewriter=True)
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="misterio", title="Señal", genre="detective",
                           tone="tenso", premise="Una señal oculta la verdad", target_words=450)
    with pytest.raises(RuntimeError, match="reescritor"):
        StoryGenerator(provider, tmp_path / "stories", schema_repository=schemas).generate(request)
    run_dir = next((tmp_path / "stories").iterdir())
    assert (run_dir / "draft.md").is_file()
    assert (run_dir / "craft_revisions" / "attempt-0-audit.json").is_file()
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"


def test_invalid_node_review_consumes_attempt_and_generation_recovers(tmp_path):
    provider = InvalidNodeReviewProvider(1)
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="misterio", title="Señal", genre="detective",
                           tone="tenso", premise="Una señal oculta la verdad", target_words=450)
    result = StoryGenerator(provider, tmp_path / "stories", schema_repository=schemas).generate(request)
    checkpoint = json.loads(
        (result.run_dir / "planning_checkpoint" / "node_reviews.json").read_text(encoding="utf-8")
    )
    invalid = next(item for item in checkpoint["rejected"] if item.get("stage") == "review")
    assert invalid["validation"]["schema"] == "PlotNodeReview"
    assert invalid["validation"]["structured_attempts"] == 2
    assert provider.review_calls == 3


def test_invalid_node_reviews_exhaust_as_storyline_error_with_checkpoints(tmp_path):
    provider = InvalidNodeReviewProvider(99)
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="misterio", title="Señal", genre="detective",
                           tone="tenso", premise="Una señal oculta la verdad", target_words=450)
    generator = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas, max_cpn_retries=1,
    )
    with pytest.raises(StorylinePlanningError):
        generator.generate(request)
    run_dir = next((tmp_path / "stories").iterdir())
    checkpoint = run_dir / "planning_checkpoint" / "node_reviews.json"
    assert checkpoint.is_file()
    reviews = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert len(reviews["rejected"]) == 2
    error = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert error["code"] == "STORYLINE_PLANNING_FAILED"
    assert error["details"]["attempts"] == 2


def test_comparison_sheet_contains_both_stories(tmp_path):
    left, right = tmp_path / "left.md", tmp_path / "right.md"
    left.write_text("Historia anterior", encoding="utf-8")
    right.write_text("Historia nueva", encoding="utf-8")
    output = build_comparison(left, right, tmp_path / "comparison.html")
    content = output.read_text(encoding="utf-8")
    assert "Historia anterior" in content and "Historia nueva" in content
