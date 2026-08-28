from asg_console.visualizer import EscapeRoomVisualizer
from asg_escape_room import EscapeRoomModel


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeKeyboard:
    def __init__(self, keys=()) -> None:
        self.keys = list(keys)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def poll(self):
        return self.keys.pop(0) if self.keys else None


class FakeTerminal:
    def __init__(self) -> None:
        self.frames = []

    def draw(self, content: str) -> None:
        self.frames.append(content)


def test_controls_pause_step_view_speed_and_quit(room) -> None:
    model = EscapeRoomModel(room, seed=1)
    terminal = FakeTerminal()
    visualizer = EscapeRoomVisualizer(
        terminal=terminal,
        keyboard=FakeKeyboard([" ", "n", "v", "+", "q"]),
        clock=FakeClock(),
    )
    outcome = visualizer.run(model, tick_limit=100)
    assert outcome.cancelled
    assert model.world.tick == 1
    assert visualizer.paused
    assert visualizer.view_index == 1
    assert visualizer.interval == 1.3
    assert any("Vista: A" in frame for frame in terminal.frames)


def test_visual_result_matches_non_visual_result(room) -> None:
    model = EscapeRoomModel(room, seed=9)
    visualizer = EscapeRoomVisualizer(
        terminal=FakeTerminal(),
        keyboard=FakeKeyboard(),
        clock=FakeClock(),
        interval=0.1,
    )
    outcome = visualizer.run(model, tick_limit=100)
    assert not outcome.cancelled
    assert outcome.result is not None
    assert outcome.result.success


def test_speed_is_clamped(room) -> None:
    assert EscapeRoomVisualizer(interval=0).interval == 0.1
    assert EscapeRoomVisualizer(interval=99).interval == 5.0
