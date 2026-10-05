"""Reproducible blind assignments and comparison coverage diagnostics."""

from __future__ import annotations

import random
from collections import Counter

from .catalog import CRITERIA


def components(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Find comparison components, including isolated stories."""
    adjacency = {node: set() for node in nodes}
    for left, right in edges:
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
    groups = []
    while adjacency:
        pending = [next(iter(adjacency))]
        found = set()
        while pending:
            node = pending.pop()
            if node in found:
                continue
            found.add(node)
            pending.extend(adjacency.get(node, set()) - found)
        groups.append(sorted(found))
        for node in found:
            adjacency.pop(node, None)
    return groups


def session_questions(stories: list[str], rng: random.Random) -> list[dict]:
    """Use a shared cycle for all criteria, separating repeated pairs in the sequence."""
    cycle = list(stories)
    rng.shuffle(cycle)
    edges = list(zip(cycle, cycle[1:] + cycle[:1], strict=True))
    if len(cycle) == 2:
        edges = edges[:1]
    result = []
    criteria = list(CRITERIA)
    rng.shuffle(criteria)
    for criterion in criteria:
        rotated = list(edges)
        rng.shuffle(rotated)
        if result and set(rotated[0]) == {result[-1]["left"], result[-1]["right"]}:
            rotated = rotated[1:] + rotated[:1]
        reverse = rng.randrange(2)
        for left, right in rotated:
            if reverse:
                left, right = right, left
            result.append({"criterion": criterion, "left": left, "right": right})
    return result


def make_assignments(
    stories: list[dict], readers: list[dict], exposures: set[tuple[str, str]], seed: int
) -> list[dict]:
    """Balance eligible exposure, then search deterministic schedules for a connected graph."""
    best: tuple[tuple[int, int], list[dict]] | None = None
    for attempt in range(128):
        rng = random.Random(seed + attempt)
        appearances: Counter = Counter()
        assignments = []
        ordered = sorted(readers, key=lambda reader: reader["id"])
        rng.shuffle(ordered)
        for reader in ordered:
            eligible = [
                s
                for s in stories
                if s.get("owner") != reader["id"] and (reader["id"], s["id"]) not in exposures
            ]
            rng.shuffle(eligible)
            eligible.sort(key=lambda s: (not s["curated"], appearances[s["id"]]))
            chosen = [s["id"] for s in eligible[:10]]
            if len(chosen) < 2:
                raise ValueError("Cada lector necesita al menos dos historias desconocidas.")
            appearances.update(chosen)
            rng.shuffle(chosen)
            split = (len(chosen) + 1) // 2 if len(chosen) > 5 else len(chosen)
            blocks = [chosen[:split], chosen[split:]]
            for session, block in enumerate(blocks, 1):
                if not block:
                    continue
                for order, question in enumerate(session_questions(block, rng), 1):
                    assignments.append(
                        {
                            **question,
                            "participant": reader["id"],
                            "session": session,
                            "position": order,
                        }
                    )
        edges = [(q["left"], q["right"]) for q in assignments if q["criterion"] == "H01"]
        groups = components([s["id"] for s in stories], edges)
        shared = Counter(tuple(sorted(edge)) for edge in edges)
        quality = (len(groups), -sum(count > 1 for count in shared.values()))
        if best is None or quality < best[0]:
            best = (quality, assignments)
        if quality[0] == 1 and -quality[1] >= 3:
            break
    if best is None or best[0][0] != 1:
        raise ValueError("No se pudo conectar el conjunto: revisa lectores y exposiciones.")
    return best[1]


def coverage(story_ids: list[str], assignments: list[dict], votes: list[dict]) -> dict:
    """Report planned and effective connectivity without treating abstention as a tie."""
    result = {}
    for criterion in CRITERIA:
        planned = [q for q in assignments if q["criterion"] == criterion and not q.get("void")]
        observed = [v for v in votes if v["criterion"] == criterion]
        decided = [v for v in observed if v["choice"] != "abstain"]
        counts: Counter = Counter(s for v in decided for s in (v["left"], v["right"]))
        result[criterion] = {
            "planned": len(planned),
            "votes": len(observed),
            "abstentions": len(observed) - len(decided),
            "comparisons": {s: counts[s] for s in story_ids},
            "planned_components": components(story_ids, [(v["left"], v["right"]) for v in planned]),
            "effective_components": components(
                story_ids, [(v["left"], v["right"]) for v in decided]
            ),
        }
    return result
