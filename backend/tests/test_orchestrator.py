import asyncio

from .fakes import DRAMA_COACH_PROMPT, FakeGeminiClient
from .fakes import build_story_request
from .support import (
    create_story_record,
    create_test_engine,
    create_test_settings,
    create_user_record,
    get_story,
    list_agent_runs,
)
from app.logging_utils import configure_logging, get_pipeline_logger
from app.services.orchestrator import StoryOrchestrator


MEDIUM_PIPELINE = [
    "architect",
    "world_builder",
    "director",
    "character_simulator",
    "plot_weaver",
    "drama_coach",
    "dependency_manager",
    "coordinator_chapter_1",
    "chapter_writer_1",
    "coordinator_chapter_2",
    "chapter_writer_2",
    "coordinator_chapter_3",
    "chapter_writer_3",
    "quality_evaluator",
]
EFFICIENT_MEDIUM_PIPELINE = [
    "planning_room",
    "chapter_writer_batch",
    "quality_evaluator",
]


def test_orchestrator_uses_efficient_pipeline_by_default(db_path) -> None:
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "efficient@example.com")
    story = create_story_record(engine, user.id)
    llm_client = FakeGeminiClient()
    orchestrator = StoryOrchestrator(engine=engine, llm_client=llm_client)

    asyncio.run(orchestrator.process_story(story.id))

    stored_story = get_story(engine, story.id)
    runs = list_agent_runs(engine, story.id)

    assert stored_story.status == "completed"
    assert stored_story.story_text is not None
    assert [run.agent_name for run in runs] == EFFICIENT_MEDIUM_PIPELINE
    assert llm_client.call_count == 3
    assert stored_story.story_packet["quality_review"]["overall"] == 4.2
    assert len(stored_story.story_packet["chapter_drafts"]) == 3


def test_orchestrator_full_pipeline_records_all_runs(db_path) -> None:
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "orchestrator@example.com")
    story = create_story_record(engine, user.id)
    orchestrator = StoryOrchestrator(engine=engine, llm_client=FakeGeminiClient(), pipeline_mode="full")

    asyncio.run(orchestrator.process_story(story.id))

    stored_story = get_story(engine, story.id)
    runs = list_agent_runs(engine, story.id)

    assert stored_story.status == "completed"
    assert stored_story.story_text is not None
    assert [run.agent_name for run in runs] == MEDIUM_PIPELINE
    assert all(run.status == "completed" for run in runs)
    assert all(run.output_snapshot for run in runs)
    assert stored_story.story_packet["quality_review"]["overall"] == 4.2
    assert len(stored_story.story_packet["chapter_drafts"]) == 3


def test_orchestrator_writes_pipeline_log_file(db_path) -> None:
    settings = create_test_settings(db_path)
    configure_logging(settings)
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "pipeline-log@example.com")
    story = create_story_record(engine, user.id)
    orchestrator = StoryOrchestrator(engine=engine, llm_client=FakeGeminiClient(), pipeline_mode="full")

    asyncio.run(orchestrator.process_story(story.id))

    log_file = settings.log_dir and f"{settings.log_dir}/pipeline.log.txt"
    log_text = open(log_file, encoding="utf-8").read()

    assert "Se inicio la generacion de la historia" in log_text
    assert f"Se llamo al agente director story_id={story.id}" in log_text
    assert "Se compilo la historia final" in log_text
    assert "Se genero la historia" in log_text


def test_pipeline_log_file_keeps_last_100_entries(db_path) -> None:
    settings = create_test_settings(db_path)
    configure_logging(settings)
    logger = get_pipeline_logger()

    for index in range(105):
        logger.info("entrada_%03d", index)

    log_file = settings.log_dir and f"{settings.log_dir}/pipeline.log.txt"
    lines = open(log_file, encoding="utf-8").read().splitlines()

    assert len(lines) == 100
    assert "entrada_000" not in "\n".join(lines)
    assert "entrada_005" in lines[0]
    assert "entrada_104" in lines[-1]


def test_orchestrator_marks_story_failed_when_agent_raises(db_path) -> None:
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "failure@example.com")
    story = create_story_record(engine, user.id)
    orchestrator = StoryOrchestrator(
        engine=engine,
        llm_client=FakeGeminiClient(fail_on=DRAMA_COACH_PROMPT),
        pipeline_mode="full",
    )

    asyncio.run(orchestrator.process_story(story.id))

    stored_story = get_story(engine, story.id)
    runs = list_agent_runs(engine, story.id)

    assert stored_story.status == "failed"
    assert stored_story.error_message == "drama_coach: Synthetic agent failure"
    assert [run.agent_name for run in runs] == [
        "architect",
        "world_builder",
        "director",
        "character_simulator",
        "plot_weaver",
        "drama_coach",
    ]
    assert [run.status for run in runs] == ["completed", "completed", "completed", "completed", "completed", "failed"]


def test_orchestrator_writes_pipeline_log_when_agent_fails(db_path) -> None:
    settings = create_test_settings(db_path)
    configure_logging(settings)
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "pipeline-failure@example.com")
    story = create_story_record(engine, user.id)
    orchestrator = StoryOrchestrator(
        engine=engine,
        llm_client=FakeGeminiClient(fail_on=DRAMA_COACH_PROMPT),
        pipeline_mode="full",
    )

    asyncio.run(orchestrator.process_story(story.id))

    log_file = settings.log_dir and f"{settings.log_dir}/pipeline.log.txt"
    log_text = open(log_file, encoding="utf-8").read()

    assert f"Fallo el agente drama_coach story_id={story.id} error=Synthetic agent failure" in log_text
    assert f"Fallo la generacion story_id={story.id} error=drama_coach: Synthetic agent failure" in log_text


def test_orchestrator_blocks_story_when_dependency_review_is_inconsistent(db_path) -> None:
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "continuity@example.com")
    story = create_story_record(engine, user.id)
    orchestrator = StoryOrchestrator(
        engine=engine,
        llm_client=FakeGeminiClient(inconsistent_dependency=True),
        pipeline_mode="full",
    )

    asyncio.run(orchestrator.process_story(story.id))

    stored_story = get_story(engine, story.id)
    runs = list_agent_runs(engine, story.id)

    assert stored_story.status == "failed"
    assert stored_story.error_message == "dependency_manager: unresolved continuity issues"
    assert [run.agent_name for run in runs] == [
        "architect",
        "world_builder",
        "director",
        "character_simulator",
        "plot_weaver",
        "drama_coach",
        "dependency_manager",
    ]
    assert all(run.status == "completed" for run in runs)


def test_orchestrator_uses_adaptive_chapter_count(db_path) -> None:
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "short@example.com")
    story = create_story_record(engine, user.id, build_story_request(length="short"))
    orchestrator = StoryOrchestrator(engine=engine, llm_client=FakeGeminiClient(), pipeline_mode="full")

    asyncio.run(orchestrator.process_story(story.id))

    stored_story = get_story(engine, story.id)
    runs = list_agent_runs(engine, story.id)

    assert stored_story.status == "completed"
    assert len(stored_story.story_packet["chapter_plan"]["chapters"]) == 1
    assert [run.agent_name for run in runs if run.agent_name.startswith("chapter_writer")] == ["chapter_writer_1"]


def test_orchestrator_rewrites_once_when_quality_blocks(db_path) -> None:
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "rewrite@example.com")
    story = create_story_record(engine, user.id)
    orchestrator = StoryOrchestrator(engine=engine, llm_client=FakeGeminiClient(blocking_quality_once=True))

    asyncio.run(orchestrator.process_story(story.id))

    stored_story = get_story(engine, story.id)
    runs = list_agent_runs(engine, story.id)

    assert stored_story.status == "completed"
    assert stored_story.title == "El reloj de la torre muda"
    assert "quality_rewriter" in [run.agent_name for run in runs]
    assert runs[-1].agent_name == "quality_evaluator_revision"
    assert stored_story.story_packet["quality_review"]["blocking_issues"] == []


def test_orchestrator_fails_when_quality_block_persists(db_path) -> None:
    engine = create_test_engine(db_path)
    user = create_user_record(engine, "quality-failure@example.com")
    story = create_story_record(engine, user.id)
    orchestrator = StoryOrchestrator(engine=engine, llm_client=FakeGeminiClient(blocking_quality_always=True))

    asyncio.run(orchestrator.process_story(story.id))

    stored_story = get_story(engine, story.id)
    runs = list_agent_runs(engine, story.id)

    assert stored_story.status == "failed"
    assert stored_story.error_message == "quality_evaluator: unresolved blocking issues"
    assert runs[-1].agent_name == "quality_evaluator_revision"
