import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Dashboard } from "./dashboard";
import { apiRequest } from "@/lib/api";
import { AuthResponse, StoryListItem } from "@/lib/types";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiRequest: vi.fn(),
  };
});

vi.mock("./auth-panel", () => ({
  AuthPanel: ({ onAuthenticated }: { onAuthenticated: (response: AuthResponse) => void }) => (
    <button onClick={() => onAuthenticated({ user: { id: "user-1", email: "writer@example.com" } })} type="button">
      Mock auth panel
    </button>
  ),
}));

vi.mock("./story-composer", () => ({
  StoryComposer: () => <div>Mock composer</div>,
}));

vi.mock("./story-library", () => ({
  StoryLibrary: ({ stories }: { stories: StoryListItem[] }) => <div>library-count:{stories.length}</div>,
}));

vi.mock("./story-highlights", () => ({
  StoryHighlights: ({ stories }: { stories: StoryListItem[] }) => (
    <div>highlight-statuses:{stories.map((story) => story.status).join(",")}</div>
  ),
}));

const apiRequestMock = vi.mocked(apiRequest);

const activeStory: StoryListItem = {
  id: "story-1",
  title: "Historia activa",
  summary: "Resumen",
  style: "Fantasia",
  plot: "Trama activa",
  length: "medium",
  language: "es",
  status: "running",
  current_stage: "Plot Weaver",
  progress_percent: 42,
  evaluation: null,
  created_at: "2026-03-15T10:00:00Z",
  updated_at: "2026-03-15T10:00:00Z",
};

const completedStory: StoryListItem = {
  ...activeStory,
  status: "completed",
  current_stage: null,
  progress_percent: 100,
  evaluation: {
    coherence: 4.4,
    orchestration: 4.3,
    overall: 4.2,
    blocking_issues: [],
  },
  updated_at: "2026-03-15T10:05:00Z",
};

async function flushDashboardEffects() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("Dashboard", () => {
  afterEach(() => {
    vi.useRealTimers();
    apiRequestMock.mockReset();
  });

  it("shows the auth panel when bootstrap authentication fails", async () => {
    apiRequestMock.mockRejectedValue(new Error("unauthorized"));

    render(<Dashboard />);

    expect(await screen.findByText("Mock auth panel")).toBeInTheDocument();
  });

  it("loads stories for an authenticated user and logs out", async () => {
    apiRequestMock.mockImplementation(async (path) => {
      if (path === "/auth/me") {
        return { user: { id: "user-1", email: "writer@example.com" } };
      }
      if (path === "/stories") {
        return [completedStory];
      }
      if (path === "/auth/logout") {
        return undefined;
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    render(<Dashboard />);

    expect(await screen.findByText("Mock composer")).toBeInTheDocument();
    expect(screen.getByText("library-count:1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /cerrar sesion/i }));

    await waitFor(() =>
      expect(apiRequestMock).toHaveBeenCalledWith("/auth/logout", { method: "POST" }),
    );
    expect(await screen.findByText("Mock auth panel")).toBeInTheDocument();
  });

  it("polls while there are active stories and stops after completion", async () => {
    vi.useFakeTimers();
    let storyCalls = 0;

    apiRequestMock.mockImplementation(async (path) => {
      if (path === "/auth/me") {
        return { user: { id: "user-1", email: "writer@example.com" } };
      }
      if (path === "/stories") {
        storyCalls += 1;
        return storyCalls === 1 ? [activeStory] : [completedStory];
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    render(<Dashboard />);

    await flushDashboardEffects();
    expect(screen.getByText("highlight-statuses:running")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    await flushDashboardEffects();
    expect(screen.getByText("highlight-statuses:completed")).toBeInTheDocument();
    expect(apiRequestMock).toHaveBeenCalledTimes(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(apiRequestMock).toHaveBeenCalledTimes(3);
  });
});
