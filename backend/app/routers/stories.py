from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from app.deps import CurrentUserDep, SessionDep
from app.logging_utils import get_audit_logger
from app.models import Story, StoryAgentRun
from app.schemas import (
    AgentProgress,
    StoryDetail,
    StoryEvaluation,
    StoryEvaluationSummary,
    StoryGenerateRequest,
    StoryJobCreated,
    StoryListItem,
    StoryPacket,
)
from app.services.orchestrator import CHAPTERS_BY_LENGTH

router = APIRouter(prefix="/stories", tags=["stories"])
audit_logger = get_audit_logger()


BASE_AGENT_SEQUENCE = [
    "architect",
    "world_builder",
    "director",
    "character_simulator",
    "plot_weaver",
    "drama_coach",
    "dependency_manager",
]
EFFICIENT_AGENT_SEQUENCE = [
    "planning_room",
    "chapter_writer_batch",
    "quality_evaluator",
]
EFFICIENT_AGENT_NAMES = {*EFFICIENT_AGENT_SEQUENCE, "quality_rewriter", "quality_evaluator_revision"}

AGENT_LABELS = {
    "planning_room": "Planning Room",
    "chapter_writer_batch": "Chapter Writer Batch",
    "architect": "Architect",
    "world_builder": "World Builder",
    "director": "Director",
    "character_simulator": "Character Simulator",
    "plot_weaver": "Plot Weaver",
    "drama_coach": "Drama Coach",
    "dependency_manager": "Dependency Manager",
    "quality_evaluator": "Quality Evaluator",
    "quality_rewriter": "Quality Rewriter",
    "quality_evaluator_revision": "Quality Evaluator revision",
}


def _agent_label(agent_name: str) -> str:
    if agent_name.startswith("coordinator_chapter_"):
        return f"Coordinator/ReIO capitulo {agent_name.rsplit('_', 1)[-1]}"
    if agent_name.startswith("chapter_writer_"):
        return f"Chapter Writer capitulo {agent_name.rsplit('_', 1)[-1]}"
    return AGENT_LABELS.get(agent_name, agent_name.replace("_", " ").title())


def _expected_agent_sequence(story: Story, runs: list[StoryAgentRun] | None = None) -> list[str]:
    if runs and any(run.agent_name in EFFICIENT_AGENT_NAMES for run in runs):
        return EFFICIENT_AGENT_SEQUENCE
    if runs and any(_is_full_pipeline_run(run.agent_name) for run in runs):
        return _full_agent_sequence(story)
    if story.pipeline_mode == "efficient":
        return EFFICIENT_AGENT_SEQUENCE
    return _full_agent_sequence(story)


def _is_full_pipeline_run(agent_name: str) -> bool:
    return (
        agent_name in BASE_AGENT_SEQUENCE
        or agent_name.startswith("coordinator_chapter_")
        or (agent_name.startswith("chapter_writer_") and agent_name != "chapter_writer_batch")
    )


def _full_agent_sequence(story: Story) -> list[str]:
    chapter_count = CHAPTERS_BY_LENGTH.get(story.length, 3)
    chapter_agents = [
        agent_name
        for index in range(1, chapter_count + 1)
        for agent_name in (f"coordinator_chapter_{index}", f"chapter_writer_{index}")
    ]
    return [*BASE_AGENT_SEQUENCE, *chapter_agents, "quality_evaluator"]


def _packet_from_story(story: Story) -> StoryPacket:
    try:
        return StoryPacket.parse_obj(story.story_packet or {"input_brief": story.input_brief})
    except Exception:
        return StoryPacket(input_brief=story.input_brief or {})


def _evaluation_summary(evaluation: StoryEvaluation | None) -> StoryEvaluationSummary | None:
    if not evaluation:
        return None
    return StoryEvaluationSummary(
        coherence=evaluation.coherence,
        orchestration=evaluation.orchestration,
        overall=evaluation.overall,
        blocking_issues=evaluation.blocking_issues,
    )


def _current_stage(story: Story, runs: list[StoryAgentRun]) -> str | None:
    if story.status == "completed":
        return None
    if story.status == "failed":
        failed_run = next((run for run in reversed(runs) if run.status == "failed"), None)
        return _agent_label(failed_run.agent_name) if failed_run else "Fallida"
    running_run = next((run for run in reversed(runs) if run.status == "running"), None)
    if running_run:
        return _agent_label(running_run.agent_name)
    completed_names = {run.agent_name for run in runs if run.status == "completed"}
    next_agent = next((agent for agent in _expected_agent_sequence(story, runs) if agent not in completed_names), None)
    return _agent_label(next_agent) if next_agent else "Finalizando"


def _progress_percent(story: Story, runs: list[StoryAgentRun]) -> int:
    if story.status == "completed":
        return 100
    expected = _expected_agent_sequence(story, runs)
    if not expected:
        return 0
    completed_count = len({run.agent_name for run in runs if run.status == "completed" and run.agent_name in expected})
    percent = int((completed_count / len(expected)) * 100)
    if story.status in {"pending", "running"}:
        return min(percent, 99)
    return min(percent, 100)


def _agent_progress(runs: list[StoryAgentRun]) -> list[AgentProgress]:
    return [
        AgentProgress(
            agent_name=run.agent_name,
            label=_agent_label(run.agent_name),
            status=run.status,
            started_at=run.started_at.isoformat(),
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            error_message=run.error_message,
        )
        for run in runs
    ]


def _to_list_item(story: Story, runs: list[StoryAgentRun]) -> StoryListItem:
    packet = _packet_from_story(story)
    return StoryListItem(
        id=story.id,
        title=story.title,
        summary=story.summary,
        style=story.style,
        plot=story.plot,
        length=story.length,
        language=story.language,
        pipeline_mode=story.pipeline_mode if story.pipeline_mode in {"efficient", "full"} else "efficient",
        status=story.status,
        current_stage=_current_stage(story, runs),
        progress_percent=_progress_percent(story, runs),
        evaluation=_evaluation_summary(packet.quality_review),
        created_at=story.created_at.isoformat(),
        updated_at=story.updated_at.isoformat(),
    )


def _to_detail(story: Story, runs: list[StoryAgentRun]) -> StoryDetail:
    packet = _packet_from_story(story)
    return StoryDetail(
        id=story.id,
        title=story.title,
        summary=story.summary,
        style=story.style,
        plot=story.plot,
        length=story.length,
        language=story.language,
        pipeline_mode=story.pipeline_mode if story.pipeline_mode in {"efficient", "full"} else "efficient",
        status=story.status,
        current_stage=_current_stage(story, runs),
        progress_percent=_progress_percent(story, runs),
        evaluation=packet.quality_review,
        story_text=story.story_text,
        error_message=story.error_message,
        agent_progress=_agent_progress(runs),
        created_at=story.created_at.isoformat(),
        updated_at=story.updated_at.isoformat(),
    )


def _runs_by_story(session: SessionDep, story_ids: list[str]) -> dict[str, list[StoryAgentRun]]:
    if not story_ids:
        return {}
    runs = session.exec(
        select(StoryAgentRun)
        .where(StoryAgentRun.story_id.in_(story_ids))
        .order_by(StoryAgentRun.started_at)
    ).all()
    grouped: dict[str, list[StoryAgentRun]] = {story_id: [] for story_id in story_ids}
    for run in runs:
        grouped.setdefault(run.story_id, []).append(run)
    return grouped


@router.get("", response_model=list[StoryListItem])
def list_stories(session: SessionDep, user: CurrentUserDep):
    stories = session.exec(select(Story).where(Story.user_id == user.id).order_by(Story.created_at.desc())).all()
    grouped_runs = _runs_by_story(session, [story.id for story in stories])
    return [_to_list_item(story, grouped_runs.get(story.id, [])) for story in stories]


@router.get("/{story_id}", response_model=StoryDetail)
def get_story(story_id: str, session: SessionDep, user: CurrentUserDep):
    story = session.get(Story, story_id)
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    runs = _runs_by_story(session, [story.id]).get(story.id, [])
    return _to_detail(story, runs)


@router.post("/generate", response_model=StoryJobCreated, status_code=status.HTTP_202_ACCEPTED)
async def generate_story(
    payload: StoryGenerateRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
):
    input_brief = payload.to_input_brief()
    story = Story(
        user_id=user.id,
        style=payload.style,
        plot=payload.plot,
        length=payload.length,
        language=payload.language,
        pipeline_mode=payload.pipeline_mode,
        characters_json=[character.dict() for character in payload.characters],
        input_brief=input_brief,
        story_packet={"input_brief": input_brief},
        status="pending",
    )
    session.add(story)
    session.commit()
    session.refresh(story)

    audit_logger.info(
        "story.created story_id=%s user_id=%s email=%s style=%s length=%s",
        story.id,
        user.id,
        user.email,
        story.style,
        story.length,
    )
    await request.app.state.worker.enqueue(story.id)
    return StoryJobCreated(id=story.id, status=story.status)
