import json

from asg_top_down.generator import StoryGenerator
from asg_top_down.compare import build_comparison
from asg_top_down.incremental import IncrementalPlotPlanner
from asg_top_down.narrative_db import NarrativeSchemaRepository
from asg_top_down.schemas import (
    ArchetypeSelection, ChapterAnchors, ChapterAnchorsArtifact, ChapterPlan,
    Character, CharactersArtifact, DiagnosticAudit, PlotNodeProposal,
    PlotNodeReview, StoryOutlineArtifact, StoryPlanArtifact, StoryRequest,
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
                jungian_archetype="protagonist", goal="revelar", motivation="proteger", conflict="censura", arc="decide actuar")])
        if schema is StoryOutlineArtifact:
            return StoryOutlineArtifact(premise="Una señal censurada", synopsis="Ada encuentra y revela la señal",
                chapters=[ChapterPlan(id="ch1", order=1, title="Señal", abstract="Ada investiga",
                                      target_words=450, freytag_phases=["exposition", "climax", "denouement"])])
        if schema is ChapterAnchorsArtifact:
            return ChapterAnchorsArtifact(anchors=[ChapterAnchors(chapter_id="ch1",
                begin_subject="Ada", begin_verb="encuentra", begin_object="una señal",
                end_subject="Ada", end_verb="revela", end_object="la señal")])
        if schema is PlotNodeProposal:
            self.proposals += 1
            return PlotNodeProposal(subject="Ada", verb="descifra", object="la señal", purpose="descubrir el encubrimiento",
                schema_beat_id="escalation", preconditions=["Ada posee la señal"], effects=["Ada conoce la verdad"],
                intention="proteger a la tripulación", conflict="la censura detecta su acceso",
                state_changes=[{"entity":"Ada", "attribute":"knowledge", "value":"verdad de la señal"}])
        if schema is PlotNodeReview:
            return PlotNodeReview(accepted=True, causal=True, intentional=True, conflict_present=True,
                continuous=True, novel=True, advances_ending=True, world_consistent=True)
        if schema is DiagnosticAudit:
            return DiagnosticAudit()
        raise AssertionError(schema)

    def generate_text(self, **kwargs):
        return "Ada descifró la señal porque necesitaba proteger a la tripulación. La censura respondió."


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
            "storyline.json", "nekg.json", "node_reviews.json", "diagnostic_audit.json", "story.md"} <= names
    graph = json.loads((result.run_dir / "storyline.json").read_text(encoding="utf-8"))
    assert [node["node_type"] for node in graph["nodes"]] == ["CBN", "CPN", "CEN"]
    assert len(graph["accepted_edges"]) == 2
    nekg = json.loads((result.run_dir / "nekg.json").read_text(encoding="utf-8"))
    ada = next(entity for entity in nekg["entities"] if entity["name"] == "Ada")
    assert ada["state"]["knowledge"] == "verdad de la señal"


def test_cpn_budget_prefers_fewer_developed_events():
    chapter = ChapterPlan(id="ch", order=1, title="x", abstract="x", target_words=1500,
                          freytag_phases=["rising_action"])
    assert IncrementalPlotPlanner.cpn_budget(chapter) == 4


def test_comparison_sheet_contains_both_stories(tmp_path):
    left, right = tmp_path / "left.md", tmp_path / "right.md"
    left.write_text("Historia anterior", encoding="utf-8")
    right.write_text("Historia nueva", encoding="utf-8")
    output = build_comparison(left, right, tmp_path / "comparison.html")
    content = output.read_text(encoding="utf-8")
    assert "Historia anterior" in content and "Historia nueva" in content
