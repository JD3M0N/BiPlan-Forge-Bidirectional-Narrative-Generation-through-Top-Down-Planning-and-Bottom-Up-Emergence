"""Core invariants of the Bottom-Up escape-room simulation.

Kept deliberately small: this suite protects the handful of behaviors that
matter to the thesis (determinism, mandatory cooperation, room validation,
conflict fairness) rather than exercising every action and map combination.
"""

import json

import pytest
from asg_escape_room import EscapeRoomModel, run_simulation
from asg_escape_room.contracts import Action, ActionType, RoomConfig
from asg_escape_room.storage import save_batch
from pydantic import ValidationError


def test_simulation_is_reproducible(room) -> None:
    """Same seed and configuration must yield the same tick log."""
    first, first_model = run_simulation(room, seed=7, tick_limit=100)
    second, second_model = run_simulation(room, seed=7, tick_limit=100)
    assert first == second
    assert first_model.tick_records == second_model.tick_records


def test_baseline_solves_minimal_room(room) -> None:
    """Seed 0 on the minimal room solves every puzzle in a fixed order."""
    result, _ = run_simulation(room, seed=0, tick_limit=100)
    assert result.success
    assert result.solved_puzzles == [
        "assemble_flashlight",
        "inspect_painting",
        "open_cabinet",
        "pressure_plate_and_lever",
    ]


def test_plate_and_lever_require_different_agents_same_tick(room) -> None:
    """The exit only unlocks when two agents hold plate and lever together."""
    model = EscapeRoomModel(room)
    model.world.solved.add("open_cabinet")
    model.world.objects["lever"].owner = "A"
    model.world.objects["lever"].position = None
    model.world.characters["A"].inventory.append("lever")
    model.world.characters["A"].position = (5, 2)
    model.world.characters["B"].position = (4, 1)
    only_lever = {
        "A": Action(actor_id="A", kind=ActionType.USE, target="lever"),
        "B": Action(actor_id="B", kind=ActionType.WAIT),
    }
    model.resolve_actions(only_lever)
    assert not model.world.exit_unlocked
    together = {
        "A": Action(actor_id="A", kind=ActionType.USE, target="lever"),
        "B": Action(actor_id="B", kind=ActionType.HOLD, target="plate"),
    }
    model.resolve_actions(together)
    assert model.world.exit_unlocked


def _move_object_outside_map(data: dict) -> None:
    """Mutate the first object's position to sit outside the room bounds."""
    data["objects"][0]["position"] = [99, 99]


def _duplicate_an_identifier(data: dict) -> None:
    """Mutate the first object's id to collide with the first agent's id."""
    data["objects"][0]["id"] = data["agents"][0]["id"]


def _introduce_a_puzzle_cycle(data: dict) -> None:
    """Mutate the first puzzle to require itself, indirectly, through a cycle."""
    data["puzzles"][0]["requires"].append("inspect_painting")


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (_move_object_outside_map, "dentro del mapa"),
        (_duplicate_an_identifier, "únicos"),
        (_introduce_a_puzzle_cycle, "ciclo"),
    ],
    ids=["position-outside-map", "duplicate-identifiers", "cyclic-puzzles"],
)
def test_invalid_room_configurations_are_rejected(room, mutate, match) -> None:
    """RoomConfig rejects an out-of-map position, a duplicate id, and a puzzle cycle."""
    data = room.model_dump(mode="json")
    mutate(data)
    with pytest.raises(ValidationError, match=match):
        RoomConfig.model_validate(data)


def test_conflict_priority_rotates(room) -> None:
    """Two agents contesting the same cell do not always resolve in the same order."""
    model = EscapeRoomModel(room)
    model.world.characters["A"].position = (2, 1)
    model.world.characters["B"].position = (2, 3)
    proposals = {
        "A": Action(actor_id="A", kind=ActionType.MOVE, target=(2, 2)),
        "B": Action(actor_id="B", kind=ActionType.MOVE, target=(2, 2)),
    }
    first = model.resolve_actions(proposals)
    assert [r.action.actor_id for r in first if r.valid] == ["A"]
    model.world.characters["A"].position = (2, 1)
    model.world.characters["B"].position = (2, 3)
    model.world.tick = 1
    second = model.resolve_actions(proposals)
    assert [r.action.actor_id for r in second if r.valid] == ["B"]


def test_seed_is_random_when_omitted(tmp_path, maps_dir, monkeypatch) -> None:
    """Without --seed the CLI still persists a reproducible, evaluable run."""
    import argparse
    import json

    from asg_escape_room import cli
    from asg_escape_room.config import Settings

    monkeypatch.setattr(cli, "load_settings", lambda: Settings(None, "test-model", tmp_path))
    monkeypatch.setattr(cli.secrets, "randbits", lambda bits: 987654321)
    args = argparse.Namespace(
        map=maps_dir / "minimal_room.json",
        seed=None,
        agents=2,
        tick_limit=100,
        batch=False,
        no_llm=True,
    )
    output = cli.run_one(args)

    request = json.loads((output / "request.json").read_text(encoding="utf-8"))
    assert request["seed"] == 987654321

    evaluation = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["schema_version"] == 1
    assert evaluation["evaluations"][0]["user"] is None

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["audio_status"] == "completed"
    assert "audio" in metadata["completed_stages"]
    assert (output / "story.mp3").read_bytes() == b"fake-mp3"


def test_a_rejected_move_does_not_free_its_cell(room) -> None:
    """A blocked proposal keeps its occupant in place, so nobody may take that cell."""
    model = EscapeRoomModel(room)
    model.world.characters["A"].position = (1, 1)
    model.world.characters["B"].position = (2, 1)
    proposals = {
        # (1, 0) is a wall, so A stays on (1, 1) even though it proposed to leave.
        "A": Action(actor_id="A", kind=ActionType.MOVE, target=(1, 0)),
        "B": Action(actor_id="B", kind=ActionType.MOVE, target=(1, 1)),
    }
    resolved = {item.action.actor_id: item for item in model.resolve_actions(proposals)}
    assert resolved["A"].valid is False
    assert resolved["B"].valid is False
    assert resolved["B"].reason == "occupied"
    positions = [character.position for character in model.world.characters.values()]
    assert len(set(positions)) == len(positions)


def test_two_agents_cannot_walk_through_each_other(room) -> None:
    """Adjacent agents proposing to swap positions are both rejected."""
    model = EscapeRoomModel(room)
    model.world.characters["A"].position = (1, 1)
    model.world.characters["B"].position = (2, 1)
    proposals = {
        "A": Action(actor_id="A", kind=ActionType.MOVE, target=(2, 1)),
        "B": Action(actor_id="B", kind=ActionType.MOVE, target=(1, 1)),
    }
    resolved = {item.action.actor_id: item for item in model.resolve_actions(proposals)}
    assert [resolved["A"].valid, resolved["B"].valid] == [False, False]
    assert model.world.characters["A"].position == (1, 1)
    assert model.world.characters["B"].position == (2, 1)


def batch_rows() -> list[dict]:
    return [
        {"seed": 0, "agents": 2, "success": True, "ticks": 10},
        {"seed": 1, "agents": 2, "success": False, "ticks": 30},
        {"seed": 0, "agents": 3, "success": True, "ticks": 8},
    ]


def test_two_batches_in_the_same_second_coexist(tmp_path) -> None:
    """Second-resolution names used to overwrite the previous experiment in silence."""
    first = save_batch(tmp_path, batch_rows())
    second = save_batch(tmp_path, batch_rows())

    assert first != second
    for directory in (first, second):
        assert (directory / "runs.csv").read_text(encoding="utf-8").startswith("seed,agents")
        assert (directory / "summary.csv").is_file()
    experiments = sorted((tmp_path / "experiments").iterdir())
    assert len(experiments) == 2


def test_an_empty_batch_is_refused_without_leaving_a_directory(tmp_path) -> None:
    """main() catches ValueError; the old IndexError escaped as a traceback after mkdir."""
    with pytest.raises(ValueError, match="lote sin ejecuciones"):
        save_batch(tmp_path, [])
    assert not (tmp_path / "experiments").exists()


def test_a_batch_declares_how_to_reproduce_it(tmp_path) -> None:
    """The two CSVs alone never said which map or tick limit produced them."""
    config = {"map": "maps/minimal_room.json", "tick_limit": 50, "agent_counts": [2, 3]}
    directory = save_batch(tmp_path, batch_rows(), config)

    recorded = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
    assert recorded["map"] == "maps/minimal_room.json"
    assert recorded["tick_limit"] == 50
    assert recorded["agent_counts"] == [2, 3]
    assert recorded["runs"] == 3
    assert recorded["experiment_id"] == directory.name
    assert recorded["package_version"]
