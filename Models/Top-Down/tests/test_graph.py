import pytest
from asg_top_down.graph import CausalGraphProcessor, render_mermaid
from asg_top_down.schemas import CausalEdge
from fakes import RESPONSES
from asg_top_down.schemas import DirectedStoryArtifact


def test_cpc_removes_weak_cycle_edge_and_returns_dag() -> None:
    source = RESPONSES[DirectedStoryArtifact].model_copy(deep=True)
    source.candidate_edges.append(CausalEdge(source="beat_3", target="beat_1", relation="causes", strength=1, rationale="Ciclo débil"))
    graph = CausalGraphProcessor().process(source)
    assert graph.topological_order == ["beat_1", "beat_2", "beat_3"]
    assert [(x.edge.source, x.edge.target) for x in graph.discarded_edges] == [("beat_3", "beat_1")]
    assert "flowchart TD" in render_mermaid(graph)


def test_graph_rejects_unknown_references() -> None:
    source = RESPONSES[DirectedStoryArtifact].model_copy(deep=True)
    source.candidate_edges.append(CausalEdge(source="missing", target="beat_1", relation="causes", strength=5, rationale="Inválida"))
    with pytest.raises(ValueError, match="unknown beat"):
        CausalGraphProcessor().process(source)
