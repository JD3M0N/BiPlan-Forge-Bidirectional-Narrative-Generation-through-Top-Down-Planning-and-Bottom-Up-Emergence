import React from "react";
import { render, screen } from "@testing-library/react";

import { StoryLibrary } from "./story-library";

vi.mock("@/lib/format", () => ({
  formatDate: () => "15 mar 2026",
  storyLabel: (title: string | null, plot: string) => title ?? plot,
}));

describe("StoryLibrary", () => {
  it("renders an empty state", () => {
    render(<StoryLibrary stories={[]} />);

    expect(screen.getByText(/aun no hay historias guardadas/i)).toBeInTheDocument();
  });

  it("renders stories as links", () => {
    render(
      <StoryLibrary
        stories={[
          {
            id: "story-1",
            title: "Historia",
            summary: "Resumen",
            style: "Fantasia",
            plot: "Trama",
            length: "medium",
            language: "es",
            pipeline_mode: "efficient",
            status: "completed",
            current_stage: null,
            progress_percent: 100,
            evaluation: {
              coherence: 4.4,
              orchestration: 4.3,
              overall: 4.2,
              blocking_issues: [],
            },
            created_at: "2026-03-15T10:00:00Z",
            updated_at: "2026-03-15T10:05:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: /historia/i })).toHaveAttribute("href", "/stories/story-1");
    expect(screen.getByText("15 mar 2026")).toBeInTheDocument();
    expect(screen.getByText(/pipeline efficient/i)).toBeInTheDocument();
    expect(screen.getByText(/evaluacion 4.2\/5/i)).toBeInTheDocument();
  });
});
