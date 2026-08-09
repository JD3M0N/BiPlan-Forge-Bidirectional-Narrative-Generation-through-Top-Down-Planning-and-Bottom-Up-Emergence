import pytest

from asg_top_down.graph import StorylineGraphProcessor, StorylineValidationError, render_mermaid
from asg_top_down.schemas import NarrativeEdge, DirectedStoryArtifact
from fakes import RESPONSES


def test_cycle_edge_is_discarded_and_result_is_dag() -> None:
    source = RESPONSES[DirectedStoryArtifact].model_copy(deep=True)
    source.candidate_edges.append(NarrativeEdge(source="node_15", target="node_1", relation="causes", strength=1, rationale="cycle"))
    graph = StorylineGraphProcessor().process(source)
    assert graph.topological_order == [f"node_{i}" for i in range(1, 16)]
    assert [(x.edge.source, x.edge.target) for x in graph.discarded_edges] == [("node_15", "node_1")]
    assert "CBN" in render_mermaid(graph) and "CEN" in render_mermaid(graph)


def test_unreachable_cen_is_rejected() -> None:
    source = RESPONSES[DirectedStoryArtifact].model_copy(deep=True)
    source.candidate_edges = [x for x in source.candidate_edges if x.target != "node_3"]
    with pytest.raises(StorylineValidationError, match="unreachable"):
        StorylineGraphProcessor().process(source)


def test_unknown_reference_is_rejected() -> None:
    source = RESPONSES[DirectedStoryArtifact].model_copy(deep=True)
    source.candidate_edges.append(NarrativeEdge(source="missing", target="node_1", relation="causes", rationale="invalid"))
    with pytest.raises(StorylineValidationError, match="unknown node"):
        StorylineGraphProcessor().process(source)
