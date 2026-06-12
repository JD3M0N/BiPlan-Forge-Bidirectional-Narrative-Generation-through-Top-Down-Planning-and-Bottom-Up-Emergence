"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { StoryDetail } from "@/lib/types";

type StoryDetailViewProps = {
  storyId: string;
};

function score(value: number) {
  return value.toFixed(1);
}

function renderStoryText(storyText: string) {
  const chapters = storyText
    .split(/\n(?=##\s+)/)
    .map((chapter) => chapter.trim())
    .filter(Boolean);

  if (chapters.length <= 1) {
    return <article className="reader-copy">{storyText}</article>;
  }

  return (
    <div className="chapter-stack">
      {chapters.map((chapter, index) => {
        const [heading, ...body] = chapter.split("\n");
        const title = heading.replace(/^##\s*/, "").trim() || `Capitulo ${index + 1}`;
        return (
          <article className="chapter-block" key={`${title}-${index}`}>
            <h2>{title}</h2>
            <div className="reader-copy">{body.join("\n").trim()}</div>
          </article>
        );
      })}
    </div>
  );
}

export function StoryDetailView({ storyId }: StoryDetailViewProps) {
  const [story, setStory] = useState<StoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadStory() {
      try {
        const response = await apiRequest<StoryDetail>(`/stories/${storyId}`);
        if (isActive) {
          setStory(response);
        }
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "No se pudo cargar la historia";
        if (isActive) {
          setError(message);
        }
      }
    }

    void loadStory();

    return () => {
      isActive = false;
    };
  }, [storyId]);

  if (error) {
    return (
      <div className="reader-layout">
        <div className="reader-panel panel">
          <Link className="ghost-button" href="/">
            Volver
          </Link>
          <p className="error-text">{error}</p>
        </div>
      </div>
    );
  }

  if (!story) {
    return (
      <div className="reader-layout">
        <div className="reader-panel panel">
          <p className="muted">Cargando historia...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="reader-layout">
      <div className="reader-panel panel">
        <div className="button-row">
          <Link className="ghost-button" href="/">
            Volver a la biblioteca
          </Link>
          <span className={`status-pill ${story.status}`}>{story.status}</span>
        </div>

        <div className="reader-title">
          <h1>{story.title ?? "Historia sin titulo"}</h1>
          <p className="muted">{story.summary ?? story.plot}</p>
        </div>

        <div className="reader-meta">
          <p>{formatDate(story.updated_at)}</p>
          <p>{story.style}</p>
          <p>{story.length}</p>
          <p>{story.language.toUpperCase()}</p>
        </div>

        <div className="progress-panel">
          <div className="section-title">
            <div>
              <h2>Pipeline</h2>
              <p className="muted">
                {story.current_stage ?? "Sin etapa activa"} - {story.progress_percent}%
              </p>
            </div>
          </div>
          <div className="progress-row" aria-label={`Progreso ${story.progress_percent}%`}>
            <span style={{ width: `${story.progress_percent}%` }} />
          </div>
          <div className="agent-timeline">
            {story.agent_progress.length === 0 ? (
              <p className="muted tiny">Aun no hay ejecuciones registradas.</p>
            ) : null}
            {story.agent_progress.map((agent) => (
              <div className="agent-step" key={`${agent.agent_name}-${agent.started_at}`}>
                <span className={`status-dot ${agent.status}`} />
                <div>
                  <strong>{agent.label}</strong>
                  <p className="muted tiny">
                    {agent.status}
                    {agent.error_message ? ` - ${agent.error_message}` : ""}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {story.evaluation ? (
          <div className="evaluation-panel">
            <div className="section-title">
              <div>
                <h2>Evaluacion</h2>
                <p className="muted">HANNA + orquestacion narrativa</p>
              </div>
              <span className="status-pill completed">{score(story.evaluation.overall)}/5</span>
            </div>
            <div className="score-grid">
              <p>Relevancia {score(story.evaluation.relevance)}</p>
              <p>Coherencia {score(story.evaluation.coherence)}</p>
              <p>Empatia {score(story.evaluation.empathy)}</p>
              <p>Sorpresa {score(story.evaluation.surprise)}</p>
              <p>Enganche {score(story.evaluation.engagement)}</p>
              <p>Complejidad {score(story.evaluation.complexity)}</p>
              <p>Orquestacion {score(story.evaluation.orchestration)}</p>
            </div>
            {story.evaluation.blocking_issues.length > 0 ? (
              <p className="error-text">{story.evaluation.blocking_issues.join(" ")}</p>
            ) : null}
            {story.evaluation.notes.length > 0 ? (
              <p className="muted tiny">{story.evaluation.notes.join(" ")}</p>
            ) : null}
          </div>
        ) : null}

        {story.status === "completed" && story.story_text ? (
          renderStoryText(story.story_text)
        ) : null}

        {story.status === "failed" ? (
          <p className="error-text">{story.error_message ?? "La historia fallo durante la generacion."}</p>
        ) : null}

        {story.status === "pending" || story.status === "running" ? (
          <p className="muted">
            El equipo de escritores sigue trabajando. Vuelve a esta pagina en unos segundos para leer el texto final.
          </p>
        ) : null}
      </div>
    </div>
  );
}
