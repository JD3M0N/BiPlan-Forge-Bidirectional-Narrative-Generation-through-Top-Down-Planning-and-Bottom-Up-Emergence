import asyncio
from contextlib import suppress
from datetime import datetime, timezone

from sqlmodel import Session

from app.logging_utils import get_logger, get_pipeline_logger
from app.models import Story, StoryAgentRun
from app.schemas import (
    ChapterDraft,
    ContextSummary,
    FinalStory,
    StoryPacket,
)
from app.services.agents import StoryAgents


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


CHAPTERS_BY_LENGTH = {"short": 1, "medium": 3, "long": 5}


def _upsert_context(items: list[ContextSummary], next_item: ContextSummary) -> list[ContextSummary]:
    remaining = [item for item in items if item.chapter_index != next_item.chapter_index]
    return sorted([*remaining, next_item], key=lambda item: item.chapter_index)


def _upsert_draft(items: list[ChapterDraft], next_item: ChapterDraft) -> list[ChapterDraft]:
    remaining = [item for item in items if item.chapter_index != next_item.chapter_index]
    return sorted([*remaining, next_item], key=lambda item: item.chapter_index)


def _compile_final_story(packet: StoryPacket) -> FinalStory:
    outline = packet.architect_outline
    title = outline.premise.strip().rstrip(".") if outline else "Historia generada"
    if len(title) > 90:
        title = f"{title[:87].rstrip()}..."
    summary = outline.synopsis if outline else packet.input_brief.get("plot", "")
    chapters = sorted(packet.chapter_drafts, key=lambda draft: draft.chapter_index)
    story_text = "\n\n".join(f"## {draft.title}\n\n{draft.text}" for draft in chapters)
    return FinalStory(title=title, summary=summary, story_text=story_text)


class StoryOrchestrator:
    def __init__(self, engine, llm_client, pipeline_mode: str = "efficient") -> None:
        self.engine = engine
        self.agents = StoryAgents(llm_client)
        self.pipeline_mode = pipeline_mode if pipeline_mode in {"efficient", "full"} else "efficient"
        self.logger = get_logger("orchestrator")
        self.pipeline_logger = get_pipeline_logger()

    async def process_story(self, story_id: str) -> None:
        with Session(self.engine) as session:
            story = session.get(Story, story_id)
            if not story:
                return

            story.status = "running"
            story.updated_at = utc_now()
            session.add(story)
            session.commit()
            self.logger.info("story_started story_id=%s user_id=%s", story.id, story.user_id)
            self.pipeline_logger.info("Se inicio la generacion de la historia story_id=%s", story.id)

        try:
            await self._run_pipeline(story_id)
        except Exception as exc:
            self.logger.exception("story_failed story_id=%s error=%s", story_id, exc)
            with Session(self.engine) as session:
                story = session.get(Story, story_id)
                error_message = str(exc)
                if story:
                    story.status = "failed"
                    if not story.error_message:
                        story.error_message = str(exc)
                    error_message = story.error_message
                    story.updated_at = utc_now()
                    session.add(story)
                    session.commit()
                self.pipeline_logger.info("Fallo la generacion story_id=%s error=%s", story_id, error_message)

    async def _run_pipeline(self, story_id: str) -> None:
        if self.pipeline_mode == "full":
            await self._run_full_pipeline(story_id)
            return
        await self._run_efficient_pipeline(story_id)

    async def _run_efficient_pipeline(self, story_id: str) -> None:
        with Session(self.engine) as session:
            story = session.get(Story, story_id)
            if not story:
                return
            packet = StoryPacket.parse_obj(story.story_packet or {"input_brief": story.input_brief})
            story_length = story.length

        chapter_count = CHAPTERS_BY_LENGTH.get(story_length, 3)
        planning = await self._run_agent(
            story_id,
            "planning_room",
            packet,
            lambda current_packet: self.agents.run_planning_room(current_packet, chapter_count),
        )
        packet.architect_outline = planning.architect_outline
        packet.world_bible = planning.world_bible
        packet.director_plan = planning.director_plan
        packet.simulation_log = planning.simulation_log
        packet.event_graph = planning.event_graph
        packet.entity_graph = planning.entity_graph
        packet.chapter_plan = planning.chapter_plan
        packet.drama_revision = planning.drama_revision
        packet.dependency_review = planning.dependency_review
        await self._persist_packet(story_id, packet)

        if not planning.dependency_review.is_consistent and not planning.dependency_review.fixes_applied:
            raise RuntimeError("dependency_manager: unresolved continuity issues")
        if not packet.chapter_plan:
            raise RuntimeError("plot_weaver: missing chapter plan")

        drafts = await self._run_agent(story_id, "chapter_writer_batch", packet, self.agents.run_chapter_writer_batch)
        packet.chapter_drafts = sorted(drafts.chapters, key=lambda draft: draft.chapter_index)
        await self._persist_packet(story_id, packet)

        await self._finalize_story(story_id, packet)

    async def _run_full_pipeline(self, story_id: str) -> None:
        with Session(self.engine) as session:
            story = session.get(Story, story_id)
            if not story:
                return
            packet = StoryPacket.parse_obj(story.story_packet or {"input_brief": story.input_brief})
            story_length = story.length

        architect = await self._run_agent(story_id, "architect", packet, self.agents.run_architect)
        packet.architect_outline = architect
        await self._persist_packet(story_id, packet)

        world = await self._run_agent(story_id, "world_builder", packet, self.agents.run_world_builder)
        packet.world_bible = world
        await self._persist_packet(story_id, packet)

        director = await self._run_agent(story_id, "director", packet, self.agents.run_director)
        packet.director_plan = director
        await self._persist_packet(story_id, packet)

        simulation = await self._run_agent(
            story_id,
            "character_simulator",
            packet,
            self.agents.run_character_simulator,
        )
        packet.simulation_log = simulation
        await self._persist_packet(story_id, packet)

        chapter_count = CHAPTERS_BY_LENGTH.get(story_length, 3)
        weave = await self._run_agent(
            story_id,
            "plot_weaver",
            packet,
            lambda current_packet: self.agents.run_plot_weaver(current_packet, chapter_count),
        )
        packet.event_graph = weave.event_graph
        packet.entity_graph = weave.entity_graph
        packet.chapter_plan = weave.chapter_plan
        await self._persist_packet(story_id, packet)

        drama = await self._run_agent(story_id, "drama_coach", packet, self.agents.run_drama_coach)
        packet.drama_revision = drama
        await self._persist_packet(story_id, packet)

        dependency = await self._run_agent(
            story_id,
            "dependency_manager",
            packet,
            self.agents.run_dependency_manager,
        )
        packet.dependency_review = dependency
        await self._persist_packet(story_id, packet)
        if not dependency.is_consistent and not dependency.fixes_applied:
            raise RuntimeError("dependency_manager: unresolved continuity issues")

        if not packet.chapter_plan:
            raise RuntimeError("plot_weaver: missing chapter plan")

        for chapter in packet.chapter_plan.chapters:
            context = await self._run_agent(
                story_id,
                f"coordinator_chapter_{chapter.index}",
                packet,
                lambda current_packet, current_chapter=chapter: self.agents.run_coordinator(
                    current_packet,
                    current_chapter,
                ),
            )
            packet.context_summaries = _upsert_context(packet.context_summaries, context)
            await self._persist_packet(story_id, packet)

            draft = await self._run_agent(
                story_id,
                f"chapter_writer_{chapter.index}",
                packet,
                lambda current_packet, current_context=context: self.agents.run_chapter_writer(
                    current_packet,
                    current_context,
                ),
            )
            packet.chapter_drafts = _upsert_draft(packet.chapter_drafts, draft)
            await self._persist_packet(story_id, packet)

        await self._finalize_story(story_id, packet)

    async def _finalize_story(self, story_id: str, packet: StoryPacket) -> None:
        self.pipeline_logger.info("Se empezo a compilar la historia final story_id=%s", story_id)
        packet.final_story = _compile_final_story(packet)
        self.pipeline_logger.info("Se compilo la historia final story_id=%s", story_id)
        quality = await self._run_agent(story_id, "quality_evaluator", packet, self.agents.run_quality_evaluator)
        packet.quality_review = quality
        await self._persist_packet(story_id, packet)

        if quality.blocking_issues:
            rewritten_story = await self._run_agent(
                story_id,
                "quality_rewriter",
                packet,
                self.agents.run_quality_rewriter,
            )
            packet.final_story = rewritten_story
            await self._persist_packet(story_id, packet)

            revision_quality = await self._run_agent(
                story_id,
                "quality_evaluator_revision",
                packet,
                self.agents.run_quality_evaluator,
            )
            packet.quality_review = revision_quality
            await self._persist_packet(story_id, packet)
            if revision_quality.blocking_issues:
                raise RuntimeError("quality_evaluator: unresolved blocking issues")

        await self._persist_packet(story_id, packet, completed=True)

    async def _run_agent(self, story_id: str, agent_name: str, packet: StoryPacket, runner):
        with Session(self.engine) as session:
            run = StoryAgentRun(
                story_id=story_id,
                agent_name=agent_name,
                status="running",
                input_snapshot=packet.dict(),
                started_at=utc_now(),
            )
            session.add(run)
            session.commit()
            session.refresh(run)

        if agent_name == "quality_rewriter":
            self.pipeline_logger.info("Se llamo al reescritor de calidad story_id=%s", story_id)
        self.pipeline_logger.info("Se llamo al agente %s story_id=%s", agent_name, story_id)

        try:
            output = await runner(packet)
        except Exception as exc:
            self.pipeline_logger.info("Fallo el agente %s story_id=%s error=%s", agent_name, story_id, exc)
            with Session(self.engine) as session:
                run = session.get(StoryAgentRun, run.id)
                if run:
                    run.status = "failed"
                    run.error_message = str(exc)
                    run.finished_at = utc_now()
                    session.add(run)
                story = session.get(Story, story_id)
                if story:
                    story.status = "failed"
                    story.error_message = f"{agent_name}: {exc}"
                    story.updated_at = utc_now()
                    session.add(story)
                session.commit()
            raise

        with Session(self.engine) as session:
            run = session.get(StoryAgentRun, run.id)
            if run:
                run.status = "completed"
                run.output_snapshot = output.dict()
                run.finished_at = utc_now()
                session.add(run)
                session.commit()

        self.pipeline_logger.info("El agente %s termino correctamente story_id=%s", agent_name, story_id)
        return output

    async def _persist_packet(self, story_id: str, packet: StoryPacket, completed: bool = False) -> None:
        with Session(self.engine) as session:
            story = session.get(Story, story_id)
            if not story:
                return

            story.story_packet = packet.dict()
            story.updated_at = utc_now()
            if completed and packet.final_story:
                story.status = "completed"
                story.title = packet.final_story.title
                story.summary = packet.final_story.summary
                story.story_text = packet.final_story.story_text
                story.error_message = None
                self.logger.info("story_completed story_id=%s title=%s", story.id, story.title)
                self.pipeline_logger.info("Se genero la historia story_id=%s title=%s", story.id, story.title)
            session.add(story)
            session.commit()
            self.pipeline_logger.info("Se guardo el avance de la historia story_id=%s", story.id)


class StoryWorker:
    def __init__(self, orchestrator: StoryOrchestrator) -> None:
        self.orchestrator = orchestrator
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.logger = get_logger("worker")

    async def start(self) -> None:
        if self.task is None:
            self.task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self.task is None:
            return
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task
        self.task = None

    async def enqueue(self, story_id: str) -> None:
        await self.queue.put(story_id)
        self.logger.info("story_enqueued story_id=%s queue_size=%s", story_id, self.queue.qsize())

    async def _run_loop(self) -> None:
        while True:
            story_id = await self.queue.get()
            try:
                self.logger.info("story_dequeued story_id=%s queue_size=%s", story_id, self.queue.qsize())
                await self.orchestrator.process_story(story_id)
            finally:
                self.queue.task_done()
