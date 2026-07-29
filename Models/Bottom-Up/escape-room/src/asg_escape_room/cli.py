"""CLI para ejecuciones individuales y experimentos reproducibles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import find_project_root, load_settings
from .engine import run_simulation
from .narrative import GeminiNarrativeProvider, generate_story
from .storage import RunRepository, result_row, save_batch
from .world import load_room


def parser() -> argparse.ArgumentParser:
    root = find_project_root()
    default_map = root / "Models" / "Bottom-Up" / "escape-room" / "maps" / "escape_room.json"
    result = argparse.ArgumentParser(description="Escape Room Multiagente Bottom-Up")
    result.add_argument("--map", type=Path, default=default_map)
    result.add_argument("--seed", type=int, default=0)
    result.add_argument("--agents", type=int, choices=(2, 3), default=2)
    result.add_argument("--tick-limit", type=int, default=300)
    result.add_argument("--batch", action="store_true", help="Ejecuta semillas 0–29 con 2 y 3 agentes")
    result.add_argument("--no-llm", action="store_true", help="Usa directamente el narrador de respaldo")
    return result


def room_with_agents(path: Path, count: int):
    room = load_room(path)
    if len(room.agents) < count:
        raise ValueError(f"El mapa solo define {len(room.agents)} agentes")
    return room.model_copy(update={"agents": room.agents[:count]}, deep=True)


def run_one(args: argparse.Namespace) -> Path:
    settings = load_settings()
    room = room_with_agents(args.map, args.agents)
    repository = RunRepository(settings.output_root, room.name, settings.model)
    try:
        repository.save_json(
            "request.json",
            {
                "map": str(args.map.resolve()),
                "seed": args.seed,
                "agents": args.agents,
                "tick_limit": args.tick_limit,
            },
        )
        repository.save_json("initial_world.json", room)
        repository.save_json(
            "characters.json", [agent.model_dump(mode="json") for agent in room.agents]
        )
        repository.complete_stage("configuration")
        result, model = run_simulation(
            room, seed=args.seed, tick_limit=args.tick_limit
        )
        repository.save_ticks(model.tick_records)
        repository.save_json("events.json", model.event_log)
        repository.save_json("result.json", result)
        repository.save_json("metrics.json", result.metrics)
        repository.complete_stage("simulation")
        provider = None
        if not args.no_llm and settings.api_key:
            provider = GeminiNarrativeProvider(settings.api_key, settings.model)
        story, narrator, error = generate_story(result, model.event_log, provider)
        repository.save_text("story.md", story)
        repository.complete_stage("narrative")
        repository.complete(narrator, error)
        return repository.run_dir
    except Exception as exc:
        repository.fail(str(exc))
        raise


def run_batch(args: argparse.Namespace) -> Path:
    settings = load_settings()
    rows = []
    for agents in (2, 3):
        room = room_with_agents(args.map, agents)
        for seed in range(30):
            result, _ = run_simulation(room, seed=seed, tick_limit=args.tick_limit)
            rows.append(result_row(result, agents))
    return save_batch(settings.output_root, rows)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        output = run_batch(args) if args.batch else run_one(args)
        print(f"Resultado guardado en: {output}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Ejecución cancelada.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

