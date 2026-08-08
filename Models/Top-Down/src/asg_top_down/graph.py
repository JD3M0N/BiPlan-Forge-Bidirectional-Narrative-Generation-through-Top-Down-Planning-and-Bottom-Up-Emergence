"""Deterministic causal plot-graph construction and rendering."""

from collections import defaultdict
import re

from .schemas import (
    CausalEdge,
    DirectedStoryArtifact,
    DiscardedEdge,
    NarrativeGraphArtifact,
)


class CausalGraphProcessor:
    """Build a maximum-priority DAG using CPC-style greedy cycle breaking."""

    def process(self, artifact: DirectedStoryArtifact) -> NarrativeGraphArtifact:
        self._validate_structure(artifact)
        beat_ids = {beat.id for beat in artifact.beats}
        adjacency: dict[str, set[str]] = {beat_id: set() for beat_id in beat_ids}
        degree = defaultdict(int)
        for edge in artifact.candidate_edges:
            degree[edge.source] += 1
            degree[edge.target] += 1

        accepted: list[CausalEdge] = []
        discarded: list[DiscardedEdge] = []
        ordered = sorted(
            artifact.candidate_edges,
            key=lambda edge: (-edge.strength, -(degree[edge.source] + degree[edge.target]), edge.source, edge.target),
        )
        for edge in ordered:
            if self._reachable(adjacency, edge.target, edge.source):
                discarded.append(DiscardedEdge(edge=edge, reason="would_create_cycle"))
            else:
                adjacency[edge.source].add(edge.target)
                accepted.append(edge)

        topo = self._topological_order(artifact, adjacency)
        return NarrativeGraphArtifact(
            scenes=artifact.scenes,
            beats=artifact.beats,
            candidate_edges=artifact.candidate_edges,
            accepted_edges=accepted,
            discarded_edges=discarded,
            topological_order=topo,
        )

    @staticmethod
    def _validate_structure(artifact: DirectedStoryArtifact) -> None:
        scene_ids = [scene.id for scene in artifact.scenes]
        beat_ids = [beat.id for beat in artifact.beats]
        if len(scene_ids) != len(set(scene_ids)) or len(beat_ids) != len(set(beat_ids)):
            raise ValueError("Scene and beat IDs must be unique")
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", item_id) for item_id in [*scene_ids, *beat_ids]):
            raise ValueError("Scene and beat IDs must be Mermaid-safe identifiers")
        if [scene.order for scene in artifact.scenes] != list(range(1, len(scene_ids) + 1)):
            raise ValueError("Scene order must be contiguous and start at 1")
        if [beat.global_order for beat in artifact.beats] != list(range(1, len(beat_ids) + 1)):
            raise ValueError("Global beat order must be contiguous and start at 1")
        known_beats = set(beat_ids)
        assigned: list[str] = []
        beat_by_id = {beat.id: beat for beat in artifact.beats}
        for scene in artifact.scenes:
            local_orders = [beat_by_id[x].local_order for x in scene.beat_ids if x in beat_by_id]
            if any(x not in known_beats for x in scene.beat_ids):
                raise ValueError(f"Scene {scene.id} references an unknown beat")
            if local_orders != list(range(1, len(scene.beat_ids) + 1)):
                raise ValueError(f"Scene {scene.id} beat order must be contiguous")
            if any(beat_by_id[x].scene_id != scene.id for x in scene.beat_ids):
                raise ValueError(f"Scene {scene.id} contains a beat assigned elsewhere")
            assigned.extend(scene.beat_ids)
        if len(assigned) != len(set(assigned)) or set(assigned) != known_beats:
            raise ValueError("Every beat must belong to exactly one scene")
        for edge in artifact.candidate_edges:
            if edge.source not in known_beats or edge.target not in known_beats:
                raise ValueError("Causal edge references an unknown beat")
            if edge.source == edge.target:
                raise ValueError("Self-referential causal edges are not allowed")

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
    def _topological_order(artifact: DirectedStoryArtifact, adjacency: dict[str, set[str]]) -> list[str]:
        narrative_order = {beat.id: beat.global_order for beat in artifact.beats}
        indegree = {node: 0 for node in adjacency}
        for targets in adjacency.values():
            for target in targets:
                indegree[target] += 1
        ready = sorted((n for n, d in indegree.items() if d == 0), key=narrative_order.get)
        result: list[str] = []
        while ready:
            node = ready.pop(0)
            result.append(node)
            for target in sorted(adjacency[node], key=narrative_order.get):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort(key=narrative_order.get)
        if len(result) != len(adjacency):
            raise ValueError("CPC processor failed to produce a DAG")
        return result


def render_mermaid(graph: NarrativeGraphArtifact) -> str:
    beat_by_id = {beat.id: beat for beat in graph.beats}
    lines = ["# Narrative Graph", "", "```mermaid", "flowchart TD"]
    for scene in graph.scenes:
        lines.append(f'  subgraph {scene.id}["Scene {scene.order}: {scene.title}"]')
        for beat_id in scene.beat_ids:
            label = beat_by_id[beat_id].action.replace('"', "'")
            lines.append(f'    {beat_id}["{label}"]')
        lines.append("  end")
    for edge in graph.accepted_edges:
        lines.append(f"  {edge.source} -->|{edge.relation}| {edge.target}")
    lines.extend(["```", "", "## Discarded causal edges", ""])
    if graph.discarded_edges:
        lines.extend(
            f"- `{item.edge.source} -> {item.edge.target}`: {item.reason}"
            for item in graph.discarded_edges
        )
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"
