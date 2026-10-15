// Shapes returned by the Nexora API (see .claude/tasks/CONTRACTS.md).

export interface SqlEndpoint {
  server: string;
  database: string;
}

export interface RunScope {
  workspace_id: string;
  workspace_name: string | null;
  lakehouse_id: string;
  lakehouse_name: string;
  schemas: string[];
  sql_endpoint: SqlEndpoint | null;
}

export interface HistoryEntry {
  from: string | null;
  to: string;
  at: string;
  reason: string;
  actor: string;
}

export interface RunDetail {
  run_id: string;
  prompt: string;
  subject_area: string | null;
  desired_outputs: string[];
  constraints: string[];
  state: string;
  resume_state: string | null;
  scope: RunScope | null;
  created_at: string;
  updated_at: string;
  history: HistoryEntry[];
  next_action: string;
  open_questions: unknown[];
  warnings: string[];
}

export interface RunSummary {
  run_id: string;
  state: string;
  prompt_preview: string;
  created_at: string;
  created_by: Record<string, unknown> | null;
}

export interface RunList {
  items: RunSummary[];
  total: number;
}

export interface Workspace {
  id: string;
  display_name: string;
  type: string;
}

export interface Lakehouse {
  id: string;
  display_name: string;
  workspace_id: string;
  sql_endpoint: SqlEndpoint | null;
}

export interface CreateRunBody {
  prompt: string;
  subject_area?: string;
  desired_outputs: string[];
  constraints: string[];
}

export interface ScopeBody {
  workspace_id: string;
  lakehouse_id: string;
}
