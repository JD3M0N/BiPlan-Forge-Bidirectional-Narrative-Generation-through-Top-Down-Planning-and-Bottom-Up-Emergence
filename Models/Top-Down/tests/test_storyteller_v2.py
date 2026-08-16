import json
from datetime import datetime, timezone

import pytest

from asg_top_down.generator import StoryGenerator
from asg_top_down.compare import build_comparison
from asg_top_down.errors import (
    ArtifactValidationError, StorylinePlanningError, StructuredResponseError,
)
from asg_top_down.incremental import IncrementalPlotPlanner
from asg_top_down.narrative_db import NarrativeSchemaRepository
from asg_top_down.schemas import (
    ArchetypeSelection, ChapterAnchors, ChapterAnchorsArtifact, ChapterPlan,
    Character, CharacterMilestone, CharacterSliderArc, CharactersArtifact,
    CraftAuditAnswer, CraftAuditArtifact, CraftBeat, CraftContractArtifact,
    CraftPromise, LLMUsageRecord, PlotNodeProposal, PlotNodeReview, SliderRange,
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
        return " ".join(["Ada", *(["investiga"] * 449)])


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
            return " ".join([f"Revisión-{self.rewrite_calls}", *(["completa"] * 449)])
        return super().generate_text(system_instruction=system_instruction, prompt=prompt)


class CriticFailureProvider(V2Provider):
    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is CraftAuditArtifact:
            raise RuntimeError("fallo simulado del crítico")
        return super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema,
        )


class TelemetryProvider(V2Provider):
    def __init__(self):
        super().__init__()
        self.usage_records = []
        self.usage_callback = None
        self.wait_callback = None
        self.recorded = False

    def generate_structured(self, *, system_instruction, prompt, schema):
        result = super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema,
        )
        if schema is StoryPlanArtifact and not self.recorded:
            self.recorded = True
            self.wait_callback(3, "prueba")
            record = LLMUsageRecord(
                operation="structured:StoryPlanArtifact", model=self.model_name,
                timestamp=datetime.now(timezone.utc), duration_seconds=.1,
                total_tokens=7, wait_seconds=3,
            )
            self.usage_records.append(record)
            self.usage_callback(record)
        return result


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


class SemanticRepairProvider(V2Provider):
    def __init__(self, artifact: str, *, always_invalid: bool = False):
        super().__init__()
        self.artifact = artifact
        self.always_invalid = always_invalid
        self.calls = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        names = {
            StoryPlanArtifact: "story_plan",
            CharactersArtifact: "characters",
            CraftContractArtifact: "craft_contract",
            StoryOutlineArtifact: "outline",
            ChapterAnchorsArtifact: "chapter_anchors",
        }
        candidate = super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema,
        )
        if names.get(schema) != self.artifact:
            return candidate
        self.calls += 1
        if self.calls > 1 and not self.always_invalid:
            assert "SEMANTIC REPAIR REQUIRED" in prompt
            return candidate
        candidate = candidate.model_copy(deep=True)
        if schema is StoryPlanArtifact:
            candidate.archetypes.primary = "unknown-archetype"
        elif schema is CharactersArtifact:
            candidate.characters[0].importance = "supporting"
            candidate.characters[0].slider_arc = None
        elif schema is CraftContractArtifact:
            candidate.try_fail_target = 3
        elif schema is StoryOutlineArtifact:
            candidate.chapters[0].target_words = 449
        elif schema is ChapterAnchorsArtifact:
            candidate.anchors[0].chapter_id = "missing-chapter"
        return candidate


class SetupOnlyCPNProvider(V2Provider):
    def __init__(self, *, invalid_proposals: int = 0, invalid_revisions: int = 0):
        super().__init__()
        self.invalid_proposals = invalid_proposals
        self.invalid_revisions = invalid_revisions
        self.proposal_calls = 0
        self.review_calls = 0
        self.review_prompts = []

    @staticmethod
    def proposal(*, craft_beat_ids=None, character_milestone_ids=None):
        return PlotNodeProposal(
            subject="Sari", verb="entrega", object="los planos",
            purpose="Interrumpir la investigación rutinaria",
            schema_beat_id="disruption",
            preconditions=["Krox trabaja en el laboratorio"],
            effects=["Krox conoce los planos"],
            intention="Convencer a Krox de investigar el hallazgo",
            conflict="La Academia rechaza las ideas subterráneas",
            craft_beat_ids=craft_beat_ids or [],
            character_milestone_ids=character_milestone_ids or [],
        )

    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is PlotNodeProposal:
            self.proposal_calls += 1
            if self.proposal_calls <= self.invalid_proposals:
                return self.proposal(craft_beat_ids=["setup-beat"])
            return self.proposal()
        if schema is PlotNodeReview:
            self.review_calls += 1
            self.review_prompts.append(prompt)
            revised = None
            if self.review_calls <= self.invalid_revisions:
                revised = self.proposal(
                    craft_beat_ids=["setup-beat"],
                    character_milestone_ids=["start-milestone"],
                )
            return PlotNodeReview(
                accepted=True, causal=True, intentional=True, conflict_present=True,
                continuous=True, novel=True, advances_ending=True, world_consistent=True,
                revised=revised,
            )
        return super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema,
        )


def setup_only_planning_case():
    outline = StoryOutlineArtifact(
        premise="Unos planos alteran una investigación",
        synopsis="Sari entrega los planos a Krox",
        chapters=[ChapterPlan(
            id="chap_1", order=1, title="Los planos", abstract="Sari visita a Krox",
            target_words=300, freytag_phases=["exposition"],
            craft_beats=[CraftBeat(
                id="setup-beat", promise_id="plot", kind="setup",
                description="Sari descubre los planos",
            )],
            character_milestones=[CharacterMilestone(
                id="start-milestone", character_name="Krox", stage="start",
                focus_slider="proactivity", demonstrated_value=3,
                description="Krox se limita a investigar",
            )],
        )],
    )
    anchors = ChapterAnchorsArtifact(anchors=[ChapterAnchors(
        chapter_id="chap_1", begin_subject="Krox", begin_verb="analiza",
        begin_object="herramientas", end_subject="Krox", end_verb="acepta",
        end_object="el desafío",
    )])
    return outline, anchors


def test_setup_only_chapter_keeps_consumed_ids_out_of_its_single_cpn():
    provider = SetupOnlyCPNProvider()
    outline, anchors = setup_only_planning_case()

    storyline, history = IncrementalPlotPlanner(provider).plan(outline, anchors, {})

    assert [node.node_type for node in storyline.nodes] == ["CBN", "CPN", "CEN"]
    assert storyline.nodes[0].craft_beat_ids == ["setup-beat"]
    assert storyline.nodes[0].character_milestone_ids == ["start-milestone"]
    assert storyline.nodes[1].craft_beat_ids == []
    assert storyline.nodes[1].character_milestone_ids == []
    assert history.rejected == []
    assert '"available_craft_beat_ids": []' in provider.review_prompts[0]
    assert '"available_character_milestone_ids": []' in provider.review_prompts[0]


def test_invalid_proposal_ids_are_rejected_before_review_and_next_attempt_recovers():
    provider = SetupOnlyCPNProvider(invalid_proposals=1)
    outline, anchors = setup_only_planning_case()

    storyline, history = IncrementalPlotPlanner(provider, max_retries=1).plan(outline, anchors, {})

    assert len(storyline.nodes) == 3
    assert provider.proposal_calls == 2
    assert provider.review_calls == 1
    rejection = history.rejected[0]
    assert rejection["stage"] == "proposal_validation"
    assert rejection["candidate_source"] == "proposal"
    assert rejection["review"] is None
    assert "allowed: none" in rejection["issues"][0]
    assert not any("final slot" in issue.lower() for issue in rejection["issues"])


def test_invalid_revised_ids_are_diagnosed_and_next_attempt_recovers():
    provider = SetupOnlyCPNProvider(invalid_revisions=1)
    outline, anchors = setup_only_planning_case()

    storyline, history = IncrementalPlotPlanner(provider, max_retries=1).plan(outline, anchors, {})

    assert len(storyline.nodes) == 3
    assert provider.proposal_calls == 2
    assert provider.review_calls == 2
    rejection = history.rejected[0]
    assert rejection["stage"] == "candidate_validation"
    assert rejection["proposal"]["craft_beat_ids"] == []
    assert rejection["candidate"]["craft_beat_ids"] == ["setup-beat"]
    assert rejection["review"]["revised"]["character_milestone_ids"] == ["start-milestone"]
    assert rejection["candidate_source"] == "review.revised"
    assert rejection["craft_scope"]["available_craft_beat_ids"] == []


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


@pytest.mark.parametrize(
    "artifact",
    ["story_plan", "characters", "craft_contract", "outline", "chapter_anchors"],
)
def test_semantically_invalid_artifacts_are_saved_and_repaired(tmp_path, artifact):
    provider = SemanticRepairProvider(artifact)
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(
        original_prompt="misterio", title="Señal", genre="detective",
        tone="tenso", premise="Una señal oculta la verdad", target_words=450,
    )

    result = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas,
    ).generate(request)

    attempt = result.run_dir / "artifact_attempts" / artifact / "attempt-001.json"
    validation = attempt.with_name("attempt-001-validation.json")
    assert attempt.is_file() and validation.is_file()
    assert provider.calls == 2
    assert json.loads(validation.read_text(encoding="utf-8"))["issue"]


def test_semantic_repairs_exhaust_as_actionable_artifact_error(tmp_path):
    provider = SemanticRepairProvider("outline", always_invalid=True)
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(
        original_prompt="misterio", title="Señal", genre="detective",
        tone="tenso", premise="Una señal oculta la verdad", target_words=450,
    )
    generator = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas,
        max_artifact_retries=1,
    )

    with pytest.raises(ArtifactValidationError) as captured:
        generator.generate(request)

    run_dir = next((tmp_path / "stories").iterdir())
    error = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert captured.value.stage == "outline"
    assert error["code"] == "ARTIFACT_VALIDATION_FAILED"
    assert error["stage"] == "outline"
    assert error["details"]["artifact"] == "outline"
    assert error["details"]["attempts"] == 2
    assert (run_dir / "artifact_attempts" / "outline" / "attempt-002.json").is_file()


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
            "diagnostic_audit.json", "length_audit.json", "llm_usage.json",
            "llm_usage_summary.json", "story.md"} <= names
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
    story = (result.run_dir / "story.md").read_text(encoding="utf-8")
    assert story.count("## Señal") == 1
    length = json.loads((result.run_dir / "length_audit.json").read_text(encoding="utf-8"))
    assert length["total"]["within_tolerance"] is True
    metadata = json.loads((result.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert {"outline", "anchors", "storyline", "quality_review", "story"} <= set(
        metadata["completed_stages"]
    )


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


def test_rewriter_failure_delivers_best_draft_with_warning(tmp_path):
    provider = RevisionProvider(99, fail_rewriter=True)
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(original_prompt="misterio", title="Señal", genre="detective",
                           tone="tenso", premise="Una señal oculta la verdad", target_words=450)
    result = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas,
    ).generate(request)
    run_dir = result.run_dir
    assert (run_dir / "draft.md").is_file()
    assert (run_dir / "craft_revisions" / "attempt-0-audit.json").is_file()
    assert (run_dir / "story.md").is_file()
    assert (run_dir / "quality_warning.json").is_file()
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["warnings"]


def test_critic_failure_delivers_draft_with_synthetic_audit(tmp_path):
    provider = CriticFailureProvider()
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    request = StoryRequest(
        original_prompt="misterio", title="Señal", genre="detective",
        tone="tenso", premise="Una señal oculta la verdad", target_words=450,
    )

    result = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas,
    ).generate(request)

    assert result.story_path.is_file()
    audit = json.loads((result.run_dir / "craft_audit.json").read_text(encoding="utf-8"))
    metadata = json.loads((result.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert audit["passed"] is False
    assert metadata["status"] == "completed"
    assert "auditoría" in metadata["warnings"][0]


def test_usage_and_quota_progress_are_restored_for_v2(tmp_path):
    provider = TelemetryProvider()
    schemas = NarrativeSchemaRepository(tmp_path / "schemas.db", provider=provider)
    updates = []
    request = StoryRequest(
        original_prompt="misterio", title="Señal", genre="detective",
        tone="tenso", premise="Una señal oculta la verdad", target_words=450,
    )

    result = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas,
    ).generate(request, on_progress=updates.append)

    usage = json.loads(
        (result.run_dir / "llm_usage_summary.json").read_text(encoding="utf-8")
    )
    assert usage["calls"] == 1
    assert usage["total_tokens"] == 7
    assert usage["total_wait_seconds"] == 3
    assert any(update.stage == "rate_limit" for update in updates)
    assert provider.usage_callback is None
    assert provider.wait_callback is None


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
