from asg_escape_room import EscapeRoomModel, run_simulation
from asg_escape_room.contracts import Action, ActionType


def test_agent_never_crosses_wall(room) -> None:
    model = EscapeRoomModel(room)
    agent = model.world.characters["A"]
    agent.position = (1, 1)
    result = model.resolve_actions(
        {"A": Action(actor_id="A", kind=ActionType.MOVE, target=(0, 1))}
    )[0]
    assert not result.valid
    assert agent.position == (1, 1)


def test_closed_exit_cannot_be_crossed(room) -> None:
    model = EscapeRoomModel(room)
    agent = model.world.characters["A"]
    agent.position = (5, 2)
    result = model.resolve_actions(
        {"A": Action(actor_id="A", kind=ActionType.MOVE, target=(6, 2))}
    )[0]
    assert not result.valid


def test_conflict_priority_rotates(room) -> None:
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


def test_object_cannot_enter_two_inventories(room) -> None:
    model = EscapeRoomModel(room)
    model.world.characters["A"].position = (1, 1)
    model.world.characters["B"].position = (2, 2)
    proposals = {
        i: Action(actor_id=i, kind=ActionType.PICK_UP, target="battery")
        for i in ("A", "B")
    }
    resolved = model.resolve_actions(proposals)
    assert sum(r.valid for r in resolved) == 1
    assert sum("battery" in a.inventory for a in model.world.characters.values()) == 1


def test_at_most_one_resolved_action_per_agent(room) -> None:
    model = EscapeRoomModel(room)
    record = model.step()
    assert len(record.resolutions) == len(room.agents)
    assert len({r.action.actor_id for r in record.resolutions}) == len(room.agents)


def test_simulation_is_reproducible(room) -> None:
    first, first_model = run_simulation(room, seed=7, tick_limit=100)
    second, second_model = run_simulation(room, seed=7, tick_limit=100)
    assert first == second
    assert first_model.tick_records == second_model.tick_records


def test_simulation_terminates_at_limit(room) -> None:
    result, _ = run_simulation(room, seed=0, tick_limit=1)
    assert result.reason == "tick_limit"
    assert result.ticks == 1


def test_communication_broadcasts_discovery_to_all(maps_dir) -> None:
    from asg_escape_room import load_room

    room = load_room(maps_dir / "escape_room.json")
    model = EscapeRoomModel(room)
    model.world.characters["A"].beliefs.facts.add("new_fact")
    model.resolve_actions(
        {
            "A": Action(
                actor_id="A", kind=ActionType.COMMUNICATE, target="B"
            )
        }
    )
    assert "new_fact" in model.world.characters["B"].beliefs.facts
    assert "new_fact" in model.world.characters["C"].beliefs.facts
