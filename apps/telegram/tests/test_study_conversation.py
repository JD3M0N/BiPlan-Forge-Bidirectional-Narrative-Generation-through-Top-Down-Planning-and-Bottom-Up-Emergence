"""Blind delivery and durable resumption without Telegram network calls."""

import asyncio
import html
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from asg_evaluation.catalog import guidance
from asg_evaluation.demo import prepare_demo
from asg_evaluation.study import StudyRepository
from asg_telegram.study import StudyConversation


def test_blind_delivery_and_restart_ignore_generation_user_data(tmp_path):
    repository = prepare_demo(tmp_path / "study", readers=3)
    reader = repository.export()["participants"][0]["id"]
    bot = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())
    context = SimpleNamespace(bot=bot, user_data={"generation": "unrelated"})
    controller = StudyConversation(repository, SimpleNamespace())
    asyncio.run(controller._advance(context, 1, reader))
    question = repository.next_question(reader)
    delivery = bot.send_document.call_args.kwargs
    assert delivery["document"].getvalue().decode("utf-8") == question["left"]["text"]
    assert delivery["filename"].startswith("Relato ")
    assert "DEMO-1" not in str(delivery)
    assert "baseline" not in str(delivery)
    assert "run_path" not in str(delivery)
    context.user_data.clear()
    restarted = StudyConversation(StudyRepository(repository.path), SimpleNamespace())
    for side in ("left", "right"):
        restarted._answer(reader, ["study", "read", question["id"], question[side]["id"]])
    asyncio.run(restarted._advance(context, 1, reader))
    prompt = bot.send_message.call_args.kwargs
    assert (
        repository.info()["snapshot"]["catalog"]["questions"][question["criterion"]]
        in prompt["text"]
    )
    assert html.escape(guidance()[question["criterion"]]) in prompt["text"]
    total = repository.progress(reader)["total"]
    assert f"Pregunta 1 de {total}" in prompt["text"]
    labels = [b.text for row in prompt["reply_markup"].inline_keyboard for b in row]
    assert labels == ["A", "B", "No puedo decidir"]
    stranger = repository.export()["participants"][1]["id"]
    with pytest.raises(ValueError):
        restarted._answer(stranger, ["study", "vote", question["id"], "A"])
    restarted._answer(reader, ["study", "vote", question["id"], "abstain"])
    restarted._answer(reader, ["study", "vote", question["id"], "abstain"])
    assert len(repository.export()["votes"]) == 1
