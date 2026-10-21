"""The bot end to end, offline: four ways to create, the same idea again, the comparison of
one's own two stories, the queue and the blind study."""

import asyncio
import json
import random

import pytest
from asg_evaluation.study import StudyRepository
from asg_telegram.delivery import AUDIO_WARNING, send_story
from asg_telegram.generator import GenerationFailure, StoryOutline
from asg_telegram.handlers import StoryBot
from asg_telegram.jobs import JobQueue, StoryWorker
from asg_telegram.pairs import OwnPairs
from asg_telegram.review import OwnReview
from asg_telegram.voting import Voting
from telegram.error import BadRequest
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
    """Wire the bot to a fake Telegram, a fake generator and a real queue, study and pairs."""
    bot = FakeBot()
    queue = JobQueue(tmp_path / "jobs.sqlite3")
    study = StudyRepository(tmp_path / "estudio" / "study.sqlite3")
    # Seeded so story A is the Top-Down one.
    pairs = OwnPairs(tmp_path / "estudio" / "pares.sqlite3", rng=random.Random(1))
    generator = FakeGenerator(tmp_path / "runs", failure)
    worker = StoryWorker(bot, queue, generator, study, pairs)
    review = OwnReview(queue, pairs)
    story_bot = StoryBot(queue, worker, review, pairs)
    return bot, queue, study, generator, worker, story_bot, Voting(study), review, pairs


@pytest.mark.parametrize("story_format", ["narrative", "simulated"])
@pytest.mark.parametrize("mode", ["free", "guided"])
def test_each_way_to_create_reaches_the_generator_and_the_study(tmp_path, story_format, mode):
    bot, queue, study, generator, worker, story_bot, *_ = setup(tmp_path)
    chat = Chat(bot)

    async def scenario():
        await story_bot.create(chat.message("/crear"), chat.context)
        assert bot.buttons() == [
            f"c:o:{fmt}:{kind}" for fmt in ("narrative", "simulated") for kind in ("free", "guided")
        ]
        await story_bot.callback(chat.press(f"c:o:{story_format}:{mode}"), chat.context)
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
    # The bot recommends the same idea with the other model, starting from Top-Down.
    other = "Híbrido" if story_format == "narrative" else "Top-Down"
    assert f"la misma idea con el modelo {other}" in bot.texts()[-1]
    assert bot.buttons() == ["c:same:1", "c:menu"]
    stories = study.export()["stories"]
    assert [s["owner"] for s in stories] == [study.participant("7")]


def test_queue_keeps_one_request_per_person_recovers_once_and_reports_failures(tmp_path):
    bot, queue, study, _, worker, *_ = setup(tmp_path, GenerationFailure("Sin cuota", quota=True))
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


@pytest.mark.parametrize("failure", ["missing", "upload"], ids=["missing-mp3", "failed-upload"])
def test_audio_failure_warns_but_still_delivers_the_story(tmp_path, failure):
    bot = FakeBot()
    run = fake_run(tmp_path, "historia")
    if failure == "missing":
        (run / "story.mp3").unlink()
    else:

        async def fail_audio(**kwargs):
            raise BadRequest("audio rechazado")

        bot.send_audio = fail_audio

    assert asyncio.run(send_story(bot, 7, run))

    assert [document["document"].filename for document in bot.documents] == ["historia.md"]
    assert AUDIO_WARNING in bot.texts()
    assert any("Ada abre la puerta" in text for text in bot.texts())


def test_a_participant_compares_their_own_two_stories_step_by_step(tmp_path):
    """The tutor's method on one's own pair: A and B blind, three questions, no scores."""
    bot, queue, _, generator, worker, story_bot, _, review, pairs = setup(tmp_path)
    chat = Chat(bot)

    async def scenario():
        await review.command(chat.message("/evaluar"), chat.context)
        assert "una historia terminada de cada modelo" in bot.texts()[-1]
        await story_bot.callback(chat.press("c:o:narrative:free"), chat.context)
        await story_bot.text(chat.message("Una idea"), chat.context)
        await worker.process(queue.claim())
        await story_bot.callback(chat.press("c:same:1"), chat.context)
        await worker.process(queue.claim())
        assert bot.buttons()[0] == "e:go"
        await review.callback(chat.press("e:go"), chat.context)
        assert [d["document"].filename for d in bot.documents][-2:] == [
            "Historia A.md",
            "Historia B.md",
        ]
        pair = pairs.open_pair(7)
        await review.callback(chat.press(f"e:a:{pair['id']}:H01:A"), chat.context)
        assert "toast:Lee primero las dos historias." in bot.edits
        for side in ("A", "B"):
            await review.callback(chat.press(f"e:r:{pair['id']}:{side}"), chat.context)
        assert bot.texts()[-1].startswith("Pregunta 1 de 3. De estas dos historias")
        for criterion, choice, reason in (("H01", "A", "Más sorpresas."), ("H02", "B", None)):
            answer = chat.press(f"e:a:{pair['id']}:{criterion}:{choice}")
            await review.callback(answer, chat.context)
            assert bot.buttons() == [f"e:s:{pair['id']}"]
            if reason:
                await story_bot.text(chat.message(reason), chat.context)
            else:
                await review.callback(chat.press(f"e:s:{pair['id']}"), chat.context)
        await review.callback(chat.press(f"e:a:{pair['id']}:H03:X"), chat.context)
        await review.callback(chat.press(f"e:s:{pair['id']}"), chat.context)

    asyncio.run(scenario())
    # The hybrid repeated the Top-Down request, and the bot says at the end which was which.
    assert generator.calls == [("Una idea", "narrative"), ("Una idea", "simulated")]
    assert "La Historia A era Top-Down y la B, Híbrido." in bot.texts()[-1]
    exported = json.loads(pairs.export_json())
    assert [(p["same_idea"], p["a_format"]) for p in exported["pairs"]] == [(True, "narrative")]
    assert exported["pairs"][0]["answers"] == [
        {"criterion": "H01", "choice": "narrative", "reason": "Más sorpresas."},
        {"criterion": "H02", "choice": "simulated", "reason": None},
        {"criterion": "H03", "choice": "abstain", "reason": None},
    ]
    assert pairs.open_pair(7) is None


def test_the_blind_study_still_reads_both_stories_then_votes(tmp_path):
    bot, _, study, *_, voting, _, _ = setup(tmp_path)
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


def test_a_retired_study_never_stops_the_bot(tmp_path):
    """Found on 2026-10-20: a .env still naming a schema-4 study stopped asg-telegram."""
    import sqlite3

    from asg_telegram.app import open_study

    old = tmp_path / "study.sqlite3"
    with sqlite3.connect(old) as db:
        db.execute("PRAGMA user_version = 4")
    assert open_study(old) is None
    assert open_study(tmp_path / "nuevo.sqlite3") is not None
