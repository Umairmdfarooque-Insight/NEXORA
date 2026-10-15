// Thin client for the Nexora API. It only fetches and reports errors:
// all decisions (states, next actions, validation) come from the API.

import type {
  CreateRunBody,
  Lakehouse,
  RunDetail,
  RunList,
  ScopeBody,
  Workspace,
} from "./types.ts";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number; // 0 when the API couldn't be reached
  code: string;
  fields: Record<string, string>;

  constructor(
    status: number,
    code: string,
    message: string,
    fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }

  get unreachable(): boolean {
    return this.status === 0;
  }
}

/** Field-level messages from a 422 VALIDATION_ERROR envelope. */
function fieldMessages(details: unknown): Record<string, string> {
  const fields: Record<string, string> = {};
  const errors = (details as { errors?: unknown } | null)?.errors;
  if (Array.isArray(errors)) {
    for (const item of errors) {
      const { field, message } = item as { field?: string; message?: string };
      if (field && message && !(field in fields)) {
        fields[field] = message;
      }
    }
  }
  return fields;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(
      0,
      "NETWORK",
      `Can't reach the Nexora API at ${API_BASE_URL}. Check that it is running.`,
    );
  }

  if (response.ok) {
    return (await response.json()) as T;
  }

  let body: { error?: { code?: string; message?: string; details?: unknown } } | null =
    null;
  try {
    body = await response.json();
  } catch {
    // Not JSON: fall through to the generic message.
  }
  const error = body?.error;
  throw new ApiError(
    response.status,
    error?.code ?? "UNKNOWN",
    error?.message ?? `The API returned HTTP ${response.status}.`,
    fieldMessages(error?.details),
  );
}

export const api = {
  listRuns: () => apiFetch<RunList>("/runs?limit=200"),
  getRun: (id: string) => apiFetch<RunDetail>(`/runs/${encodeURIComponent(id)}`),
  createRun: (body: CreateRunBody) =>
    apiFetch<RunDetail>("/runs", { method: "POST", body: JSON.stringify(body) }),
  setScope: (id: string, body: ScopeBody) =>
    apiFetch<RunDetail>(`/runs/${encodeURIComponent(id)}/scope`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  listWorkspaces: () => apiFetch<Workspace[]>("/fabric/workspaces"),
  listLakehouses: (workspaceId: string) =>
    apiFetch<Lakehouse[]>(
      `/fabric/workspaces/${encodeURIComponent(workspaceId)}/lakehouses`,
    ),
};
