import React from "react";
import Link from "next/link";

import { formatDate, storyLabel } from "@/lib/format";
import { StoryListItem } from "@/lib/types";

type StoryHighlightsProps = {
  stories: StoryListItem[];
};

export function StoryHighlights({ stories }: StoryHighlightsProps) {
  if (stories.length === 0) {
    return (
      <div className="empty-state">
        Tus historias recientes apareceran aqui en cuanto el primer encargo termine de generarse.
      </div>
    );
  }

  return (
    <div className="story-grid">
      {stories.slice(0, 4).map((story) => (
        <Link className="story-card panel" href={`/stories/${story.id}`} key={story.id}>
          <div className="story-card-title">
            <h3>{storyLabel(story.title, story.plot)}</h3>
            <span className={`status-pill ${story.status}`}>{story.status}</span>
          </div>
          <p className="muted">{story.summary ?? story.plot}</p>
          <div className="progress-row" aria-label={`Progreso ${story.progress_percent}%`}>
            <span style={{ width: `${story.progress_percent}%` }} />
          </div>
          <p className="muted tiny">
            {story.current_stage ?? "Sin etapa activa"} - {story.progress_percent}%
          </p>
          <p className="muted tiny">Pipeline {story.pipeline_mode}</p>
          {story.evaluation ? (
            <p className="muted tiny">Evaluacion {story.evaluation.overall.toFixed(1)}/5</p>
          ) : null}
          <p className="muted tiny">{formatDate(story.created_at)}</p>
        </Link>
      ))}
    </div>
  );
}
