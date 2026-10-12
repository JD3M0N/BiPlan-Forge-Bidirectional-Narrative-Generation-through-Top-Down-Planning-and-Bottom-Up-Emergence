"""The bot end to end, offline: four ways to create a story, the queue, and blind voting."""

import asyncio

import pytest
from asg_evaluation.study import StudyRepository
from asg_telegram.generator import GenerationFailure, StoryOutline
from asg_telegram.handlers import StoryBot
from asg_telegram.jobs import JobQueue, StoryWorker
from asg_telegram.voting import Voting
from telegram_fakes import Chat, FakeBot, FakeGenerator, fake_run

GUIDED = [
    ("text", "El faro"),
    ("press", "w:skip"),
    ("press", "w:skip"),
    ("text", "Una farera descubre un barco fantasma."),
    ("press", "w:add"),
    ("text", "Ada"),
    ("press", "w:role:1"),
    ("press", "w:pron:1"),
    ("press", "w:skip"),
    ("text", "Teme al mar."),
    ("press", "w:next"),
    ("press", "w:skip"),
    ("press", "w:go"),
]


def setup(tmp_path, failure=None):
    """Wire the bot to a fake Telegram, a fake generator and a real queue and study."""
    bot = FakeBot()
    queue = JobQueue(tmp_path / "jobs.sqlite3")
    study = StudyRepository(tmp_path / "estudio" / "study.sqlite3")
    generator = FakeGenerator(tmp_path / "runs", failure)
    worker = StoryWorker(bot, queue, generator, study)
    voting = Voting(study)
    return bot, queue, study, generator, worker, StoryBot(queue, worker, voting), voting


@pytest.mark.parametrize("story_format", ["narrative", "simulated"])
@pytest.mark.parametrize("mode", ["free", "guided"])
def test_each_way_to_create_reaches_the_generator_and_the_study(tmp_path, story_format, mode):
    bot, queue, study, generator, worker, story_bot, _ = setup(tmp_path)
    chat = Chat(bot)

    async def scenario():
        await story_bot.create(chat.message("/crear"), chat.context)
        await story_bot.callback(chat.press(f"c:m:{story_format}"), chat.context)
        await story_bot.callback(chat.press(f"c:k:{mode}"), chat.context)
        steps = [("text", "Una idea")] if mode == "free" else GUIDED
        for kind, value in steps:
            if kind == "text":
                await story_bot.text(chat.message(value), chat.context)
            else:
                await story_bot.callback(chat.press(value), chat.context)
        await worker.process(queue.claim())

    asyncio.run(scenario())
    request, used_format = generator.calls[0]
    assert used_format == story_format
    if mode == "free":
        assert request == "Una idea"
    else:
        assert isinstance(request, StoryOutline) and request.title == "El faro"
        assert request.cast == (
            {
                "name": "Ada",
                "role": "protagonista",
                "pronoun": "ella",
                "secret": "Teme al mar.",
                "description": "",
            },
        )
    assert [d["document"].filename for d in bot.documents] == ["historia.md"]
    assert [a["audio"].filename for a in bot.audios] == ["historia.mp3"]
    assert any("Ada abre la puerta" in text for text in bot.texts())
    assert "entra en el estudio" in bot.texts()[-1]
    stories = study.export()["stories"]
    assert [s["owner"] for s in stories] == [study.participant("7")]


def test_queue_keeps_one_request_per_person_recovers_once_and_reports_failures(tmp_path):
    bot, queue, study, _, worker, _, _ = setup(tmp_path, GenerationFailure("Sin cuota", quota=True))
    first = queue.enqueue(1, 7, "narrative", "Primera")
    with pytest.raises(ValueError, match="en marcha"):
        queue.enqueue(1, 7, "simulated", "Otra")
    second = queue.enqueue(2, 8, "simulated", "Segunda")
    assert queue.ahead(second) == 1
    assert queue.claim()["id"] == first
    # A restart while running requeues the job once and closes the run it left half-written;
    # a second restart gives up.
    queue.attach_run(first, tmp_path / "cortado")
    assert [(j["status"], j["run_dir"]) for j in queue.recover()] == [
        ("queued", str(tmp_path / "cortado"))
    ]
    assert queue.claim()["id"] == first
    assert [j["status"] for j in queue.recover()] == ["failed"]
    assert queue.cancel(8) == "queued" and queue.claim() is None
    queue.enqueue(1, 7, "narrative", "Tercera")
    asyncio.run(worker.process(queue.claim()))
    assert "Sin cuota" in bot.texts()[-1] and "cuota" in bot.texts()[-1]
    assert study.export()["stories"] == []


def test_a_reader_reads_both_stories_then_votes_and_moves_on(tmp_path):
    bot, _, study, _, _, _, voting = setup(tmp_path)
    for i in range(3):
        study.add_story(fake_run(tmp_path / "runs", f"historia-{i}"))
    chat = Chat(bot, user_id=9)

    async def scenario():
        await voting.command(chat.message("/evaluar"), chat.context)
        assert "no está abierta" in bot.texts()[-1]
        study.open()
        await voting.command(chat.message("/evaluar"), chat.context)
        assert [d["document"].filename for d in bot.documents] == ["Historia A.md", "Historia B.md"]
        assert len(bot.audios) == 2
        question = study.next_question(study.participant("9"))
        await voting.callback(chat.press(f"v:a:{question['id']}:A"), chat.context)
        assert "toast:Confirma primero la lectura de ambas historias." in bot.edits
        for side in ("L", "R"):
            await voting.callback(chat.press(f"v:r:{question['id']}:{side}"), chat.context)
        assert bot.texts()[-1].startswith(question["question"])
        assert bot.buttons() == [f"v:a:{question['id']}:{c}" for c in ("A", "B", "X")]
        await voting.callback(chat.press(f"v:a:{question['id']}:A"), chat.context)

    asyncio.run(scenario())
    votes = study.export()["votes"]
    assert [(v["criterion"], v["choice"]) for v in votes] == [("H01", "A")]
    # The next question reuses the stories already read, so it is asked straight away.
    assert bot.buttons()[0].startswith("v:a:") and len(bot.documents) == 2


def test_the_adapter_asks_stagecraft_for_prose_with_audio_and_translates_failures(
    tmp_path, monkeypatch
):
    from asg_stagecraft import GenerationOptions
    from asg_stagecraft.runtime.errors import GeminiDailyQuotaError
    from asg_telegram import generator as adapter

    received = []

    class Pipeline:
        def __init__(self, options):
            self.options = options

        def generate(self, story, **kwargs):
            received.append((story, self.options))
            if story == "falla":
                raise GeminiDailyQuotaError("Se agotó la cuota diaria")
            return type("Run", (), {"run_dir": tmp_path})

    monkeypatch.setattr(
        adapter.StoryGenerator, "from_options", lambda provider, root, options: Pipeline(options)
    )
    real = object.__new__(adapter.StagecraftGenerator)
    real.settings = type("Settings", (), {"output_root": tmp_path})
    real._provider = type("Provider", (), {"usage_records": []})()
    real._options = GenerationOptions().with_changes(audio=True)
    outline = StoryOutline(plot="Trama", cast=({"name": "Ada", "role": "", "pronoun": ""},))
    assert real.generate(outline, "simulated") == tmp_path
    story, options = received[0]
    assert story.cast[0].name == "Ada" and options.story_format == "simulated" and options.audio
    with pytest.raises(GenerationFailure) as failure:
        real.generate("falla", "narrative")
    assert failure.value.quota and "cuota" in failure.value.summary
    with pytest.raises(GenerationFailure, match="name"):
        real.generate(StoryOutline(plot="Trama", cast=({"name": ""},)), "narrative")
