export type StoryStatus = "pending" | "running" | "completed" | "failed";
export type PipelineMode = "efficient" | "full";

export type CharacterInput = {
  name: string;
  role: string;
  description: string;
};

export type User = {
  id: string;
  email: string;
};

export type AuthResponse = {
  user: User;
};

export type StoryListItem = {
  id: string;
  title: string | null;
  summary: string | null;
  style: string;
  plot: string;
  length: "short" | "medium" | "long";
  language: string;
  pipeline_mode: PipelineMode;
  status: StoryStatus;
  current_stage: string | null;
  progress_percent: number;
  evaluation: StoryEvaluationSummary | null;
  created_at: string;
  updated_at: string;
};

export type StoryDetail = Omit<StoryListItem, "evaluation"> & {
  story_text: string | null;
  error_message: string | null;
  agent_progress: AgentProgress[];
  evaluation: StoryEvaluation | null;
};

export type StoryGenerateRequest = {
  characters: CharacterInput[];
  style: string;
  plot: string;
  length: "short" | "medium" | "long";
  language: string;
  pipeline_mode: PipelineMode;
};

export type StoryJobCreated = {
  id: string;
  status: StoryStatus;
};

export type AgentProgress = {
  agent_name: string;
  label: string;
  status: StoryStatus;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
};

export type StoryEvaluation = {
  relevance: number;
  coherence: number;
  empathy: number;
  surprise: number;
  engagement: number;
  complexity: number;
  orchestration: number;
  overall: number;
  blocking_issues: string[];
  notes: string[];
};

export type StoryEvaluationSummary = Pick<
  StoryEvaluation,
  "coherence" | "orchestration" | "overall" | "blocking_issues"
>;
