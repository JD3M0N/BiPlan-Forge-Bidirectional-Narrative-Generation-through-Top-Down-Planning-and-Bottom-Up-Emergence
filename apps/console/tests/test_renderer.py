from asg_console.renderer import ConsoleRenderer
from asg_escape_room import EscapeRoomModel


def test_world_view_shows_everything_and_the_agent_view_hides_the_unseen(room) -> None:
    """Fog of war only means something against the full view, so both are checked together."""
    model = EscapeRoomModel(room, seed=4)
    record = model.step()

    world = ConsoleRenderer().render(model, view="WORLD", last_record=record)
    assert "Vista: WORLD" in world
    assert "# " in world
    assert "A " in world
    assert "b " in world
    assert "Acertijos resueltos: ninguno" in world
    assert "Acciones del último tick:" in world
    assert "A:" in world
    assert "[OK]" in world

    agent = ConsoleRenderer().render(model, view="A")
    assert "Vista: A" in agent
    assert "? " in agent
    assert "  B:" not in agent
