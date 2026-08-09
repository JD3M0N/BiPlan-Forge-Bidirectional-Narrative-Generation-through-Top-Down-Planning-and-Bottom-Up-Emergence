from asg_top_down.nekg import NarrativeEntityGraph
from fakes import RESPONSES
from asg_top_down.schemas import DirectedStoryArtifact


def test_nekg_deduplicates_and_returns_recent_relations() -> None:
    graph = NarrativeEntityGraph()
    nodes = RESPONSES[DirectedStoryArtifact].nodes[:2]
    for node in [*nodes, nodes[0]]:
        graph.add_node(node)
    assert len(graph.artifact().relations) == 2
    assert graph.related("Ada")[0].timestamp == 1
