from asg_escape_room import EscapeRoomModel, run_simulation
from asg_escape_room.contracts import Action, ActionType


def test_painting_requires_working_flashlight(room) -> None:
    model = EscapeRoomModel(room)
    model.world.characters["A"].position = (2, 1)
    resolved = model.resolve_actions(
        {"A": Action(actor_id="A", kind=ActionType.INSPECT, target="painting")}
    )[0]
    assert not resolved.valid
    assert "inspect_painting" not in model.world.solved


def test_plate_and_lever_require_different_agents_same_tick(room) -> None:
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


def test_baseline_solves_minimal_room(room) -> None:
    result, _ = run_simulation(room, seed=0, tick_limit=100)
    assert result.success
    assert result.solved_puzzles == [
        "assemble_flashlight",
        "inspect_painting",
        "open_cabinet",
        "pressure_plate_and_lever",
    ]
