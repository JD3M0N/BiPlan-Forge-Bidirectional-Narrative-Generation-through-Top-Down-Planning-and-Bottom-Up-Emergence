"""Planificación de caminos sobre el conocimiento parcial del agente."""

from collections import deque

from .contracts import Position


def neighbors(position: Position) -> list[Position]:
    x, y = position
    return [(x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)]


def bfs(
    start: Position,
    goals: set[Position],
    known_cells: set[Position],
    known_walls: set[Position],
) -> list[Position]:
    if start in goals:
        return []
    queue = deque([start])
    previous: dict[Position, Position | None] = {start: None}
    found: Position | None = None
    while queue:
        current = queue.popleft()
        for nxt in neighbors(current):
            if nxt in previous or nxt in known_walls or nxt not in known_cells:
                continue
            previous[nxt] = current
            if nxt in goals:
                found = nxt
                queue.clear()
                break
            queue.append(nxt)
    if found is None:
        return []
    path: list[Position] = []
    cursor = found
    while cursor != start:
        path.append(cursor)
        cursor = previous[cursor]  # type: ignore[assignment]
    return list(reversed(path))

