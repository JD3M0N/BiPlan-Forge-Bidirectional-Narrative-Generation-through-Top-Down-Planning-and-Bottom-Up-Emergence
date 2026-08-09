"""Transactional STORYLINE DAG validation and rendering."""

from collections import defaultdict
import re

from .schemas import DirectedStoryArtifact, DiscardedEdge, NarrativeEdge, StorylineArtifact


class StorylineValidationError(ValueError):
    def __init__(self, diagnostics: list[str]) -> None:
        self.diagnostics = diagnostics
        super().__init__("; ".join(diagnostics))


class StorylineGraphProcessor:
    """Accept edges greedily, then enforce all STORYLINE invariants."""

    def process(self, artifact: DirectedStoryArtifact) -> StorylineArtifact:
        diagnostics = self._structure_errors(artifact)
        if diagnostics:
            raise StorylineValidationError(diagnostics)
        ids = {node.id for node in artifact.nodes}
        adjacency = {node_id: set() for node_id in ids}
        accepted: list[NarrativeEdge] = []
        discarded: list[DiscardedEdge] = []
        for edge in sorted(artifact.candidate_edges, key=lambda x: (-x.strength, x.source, x.target)):
            if self._reachable(adjacency, edge.target, edge.source):
                discarded.append(DiscardedEdge(edge=edge, reason="would_create_cycle"))
            else:
                adjacency[edge.source].add(edge.target)
                accepted.append(edge)
        topo = self._topological_order(artifact, adjacency)
        diagnostics = self._path_errors(artifact, adjacency, topo)
        if diagnostics:
            raise StorylineValidationError(diagnostics)
        return StorylineArtifact(
            chapters=artifact.chapters, nodes=artifact.nodes,
            candidate_edges=artifact.candidate_edges, accepted_edges=accepted,
            discarded_edges=discarded, topological_order=topo,
        )

    @staticmethod
    def _structure_errors(artifact: DirectedStoryArtifact) -> list[str]:
        errors: list[str] = []
        chapter_ids = [x.id for x in artifact.chapters]
        node_ids = [x.id for x in artifact.nodes]
        if len(chapter_ids) != len(set(chapter_ids)) or len(node_ids) != len(set(node_ids)):
            errors.append("Chapter and node IDs must be unique")
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", x) for x in [*chapter_ids, *node_ids]):
            errors.append("IDs must be Mermaid-safe")
        if [x.order for x in artifact.chapters] != list(range(1, len(chapter_ids) + 1)):
            errors.append("Chapter order must be contiguous")
        if [x.global_order for x in artifact.nodes] != list(range(1, len(node_ids) + 1)):
            errors.append("Global node order must be contiguous")
        if [x.timestamp for x in artifact.nodes] != list(range(len(node_ids))):
            errors.append("Node timestamps must be contiguous")
        known = set(node_ids)
        for edge in artifact.candidate_edges:
            if edge.source not in known or edge.target not in known:
                errors.append("Narrative edge references an unknown node")
            elif edge.source == edge.target:
                errors.append("Self-referential narrative edges are not allowed")
        by_chapter = defaultdict(list)
        for node in artifact.nodes:
            by_chapter[node.chapter_id].append(node)
            if node.chapter_id not in chapter_ids:
                errors.append(f"Node {node.id} references an unknown chapter")
        for chapter in artifact.chapters:
            nodes = by_chapter[chapter.id]
            if [x.local_order for x in nodes] != list(range(1, len(nodes) + 1)):
                errors.append(f"Chapter {chapter.id} local order must be contiguous")
            if [x.node_type for x in nodes].count("CBN") != 1 or [x.node_type for x in nodes].count("CEN") != 1:
                errors.append(f"Chapter {chapter.id} must have exactly one CBN and one CEN")
            if not nodes or nodes[0].node_type != "CBN" or nodes[-1].node_type != "CEN":
                errors.append(f"Chapter {chapter.id} must start with CBN and end with CEN")
            if not any(x.node_type == "CPN" for x in nodes):
                errors.append(f"Chapter {chapter.id} must contain at least one CPN")
            if sum(x.target_words for x in nodes) != chapter.target_words:
                errors.append(f"Chapter {chapter.id} node word quotas must equal chapter quota")
        if sum(x.target_words for x in artifact.chapters) != sum(x.target_words for x in artifact.nodes):
            errors.append("Global chapter and node quotas differ")
        return errors

    def _path_errors(self, artifact, adjacency, topo) -> list[str]:
        errors: list[str] = []
        order = {node.id: node.global_order for node in artifact.nodes}
        accepted_pairs = {(source, target) for source, targets in adjacency.items() for target in targets}
        for source, target in accepted_pairs:
            if order[source] >= order[target]:
                errors.append(f"Edge {source}->{target} contradicts narrative order")
        by_chapter = defaultdict(list)
        for node in artifact.nodes:
            by_chapter[node.chapter_id].append(node)
        for index, chapter in enumerate(artifact.chapters):
            nodes = by_chapter[chapter.id]
            begin, end = nodes[0], nodes[-1]
            if not self._reachable(adjacency, begin.id, end.id):
                errors.append(f"Chapter {chapter.id}: CEN is unreachable from CBN")
            reverse = {x.id: set() for x in artifact.nodes}
            for source, targets in adjacency.items():
                for target in targets:
                    reverse[target].add(source)
            for node in nodes[1:-1]:
                if not self._reachable(adjacency, begin.id, node.id) or not self._reachable(reverse, end.id, node.id):
                    errors.append(f"Chapter {chapter.id}: node {node.id} is not on a CBN-CEN path")
            if any(target in {x.id for x in nodes} for target in adjacency[end.id]):
                errors.append(f"Chapter {chapter.id}: CEN has an outgoing intra-chapter edge")
            if index + 1 < len(artifact.chapters):
                next_begin = by_chapter[artifact.chapters[index + 1].id][0]
                if (end.id, next_begin.id) not in accepted_pairs:
                    errors.append(f"Missing chapter transition {end.id}->{next_begin.id}")
        if topo != [x.id for x in artifact.nodes]:
            errors.append("Topological order must match timestamps and narrative order")
        return errors

    @staticmethod
    def _reachable(adjacency: dict[str, set[str]], start: str, target: str) -> bool:
        pending, visited = [start], set()
        while pending:
            node = pending.pop()
            if node == target:
                return True
            if node not in visited:
                visited.add(node)
                pending.extend(adjacency[node] - visited)
        return False

    @staticmethod
    def _topological_order(artifact, adjacency) -> list[str]:
        narrative_order = {node.id: node.global_order for node in artifact.nodes}
        indegree = {node: 0 for node in adjacency}
        for targets in adjacency.values():
            for target in targets:
                indegree[target] += 1
        ready = sorted((n for n, d in indegree.items() if d == 0), key=narrative_order.get)
        result = []
        while ready:
            node = ready.pop(0)
            result.append(node)
            for target in sorted(adjacency[node], key=narrative_order.get):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort(key=narrative_order.get)
        if len(result) != len(adjacency):
            raise StorylineValidationError(["Narrative graph contains a cycle"])
        return result


# Compatibility name.
CausalGraphProcessor = StorylineGraphProcessor


def render_mermaid(graph: StorylineArtifact) -> str:
    lines = ["# Narrative Graph", "", "```mermaid", "flowchart TD"]
    shapes = {"CBN": "([{}])", "CPN": "[{}]", "CEN": "([{}])"}
    by_id = {x.id: x for x in graph.nodes}
    for chapter in graph.chapters:
        lines.append(f'  subgraph {chapter.id}["Chapter {chapter.order}: {chapter.title}"]')
        for node in (x for x in graph.nodes if x.chapter_id == chapter.id):
            label = f"{node.node_type}: {node.subject} {node.verb} {node.object}".replace('"', "'")
            lines.append(f"    {node.id}{shapes[node.node_type].format(chr(34) + label + chr(34))}")
        lines.append("  end")
    for edge in graph.accepted_edges:
        lines.append(f"  {edge.source} -->|{edge.relation}| {edge.target}")
    lines.extend(["```", "", "## Discarded cycle-forming edges", ""])
    lines.extend([f"- `{x.edge.source} -> {x.edge.target}`" for x in graph.discarded_edges] or ["- None."])
    return "\n".join(lines) + "\n"
