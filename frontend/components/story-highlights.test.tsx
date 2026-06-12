import React from "react";
import { render, screen } from "@testing-library/react";

import { StoryHighlights } from "./story-highlights";

vi.mock("@/lib/format", () => ({
  formatDate: () => "15 mar 2026",
  storyLabel: (title: string | null, plot: string) => title ?? plot,
}));

describe("StoryHighlights", () => {
  it("renders an empty state", () => {
    render(<StoryHighlights stories={[]} />);

    expect(screen.getByText(/tus historias recientes apareceran aqui/i)).toBeInTheDocument();
  });

  it("renders the latest stories", () => {
    render(
      <StoryHighlights
        stories={[
          {
            id: "story-1",
            title: "Historia destacada",
            summary: "Resumen",
            style: "Fantasia",
            plot: "Trama",
            length: "medium",
            language: "es",
            status: "running",
            current_stage: "Plot Weaver",
            progress_percent: 42,
            evaluation: null,
            created_at: "2026-03-15T10:00:00Z",
            updated_at: "2026-03-15T10:05:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: /historia destacada/i })).toHaveAttribute(
      "href",
      "/stories/story-1",
    );
    expect(screen.getByText(/plot weaver - 42%/i)).toBeInTheDocument();
    expect(screen.getByText("15 mar 2026")).toBeInTheDocument();
  });
});
