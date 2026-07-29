from asg_escape_room.integration import apply_top_down_artifacts


def test_top_down_artifacts_overlay_narrative_identity(room) -> None:
    adapted = apply_top_down_artifacts(
        room,
        {"setting": "Una estación orbital"},
        {
            "characters": [
                {"name": "Ada", "role": "protagonista"},
                {"name": "Bruno", "role": "aliado"},
            ]
        },
    )
    assert adapted.name == "Una estación orbital"
    assert [a.id for a in adapted.agents] == ["Ada", "Bruno"]
    assert room.agents[0].id == "A"

