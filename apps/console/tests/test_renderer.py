from asg_console.renderer import ConsoleRenderer
from asg_escape_room import EscapeRoomModel


def test_world_view_shows_complete_room(room) -> None:
    model = EscapeRoomModel(room, seed=4)
    output = ConsoleRenderer().render(model, view="WORLD")
    assert "Vista: WORLD" in output
    assert "# " in output
    assert "A " in output
    assert "b " in output
    assert "Acertijos resueltos: ninguno" in output


def test_agent_view_uses_fog_of_war(room) -> None:
    model = EscapeRoomModel(room, seed=4)
    output = ConsoleRenderer().render(model, view="A")
    assert "Vista: A" in output
    assert "? " in output
    assert "  B:" not in output


def test_renderer_shows_last_resolutions(room) -> None:
    model = EscapeRoomModel(room, seed=4)
    record = model.step()
    output = ConsoleRenderer().render(model, last_record=record)
    assert "Acciones del último tick:" in output
    assert "A:" in output
    assert "[OK]" in output
