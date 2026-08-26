// Server-side API client. The FastAPI base URL never reaches the browser;
// client components go through /api/proxy/* instead. Server components call
// this directly and must present the internal key the gate expects.

import { auth } from "@/auth";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const INTERNAL_KEY = process.env.INTERNAL_API_KEY ?? "";

async function get<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (INTERNAL_KEY) headers["x-internal-key"] = INTERNAL_KEY;
  try {
    const session = await auth();
    if (session?.user?.login) headers["x-user-login"] = session.user.login;
  } catch {
    // not in a session context (e.g. local dev without auth configured)
  }
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", headers });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export interface RepoOut {
  id: number;
  full_name: string;
  default_branch: string;
  autonomy_level: "suggest" | "auto_low_risk" | "full_auto";
  indexed_at: string | null;
  run_count: number;
}

export interface RunSummary {
  id: number;
  issue_number: number;
  issue_title: string;
  repo_full_name: string;
  status: string;
  cost_usd: number;
  total_tokens: number;
  latency_ms: number;
  created_at: string;
}

export interface NodeCost {
  node: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

export interface RunDetail extends RunSummary {
  classification: {
    type: string;
    severity: number;
    confidence: number;
    reasoning_summary: string;
  } | null;
  duplicates: { issue_number: number; score: number; evidence: string }[];
  missing_info: { missing: string[]; asked_comment: string } | null;
  related_files: string[];
  suggested_assignees: { login: string; reason: string; score: number }[];
  model_routing: NodeCost[];
  graph_state: Record<string, unknown> | null;
  langfuse_trace_id: string | null;
  error: string | null;
}

export interface PendingAction {
  id: number;
  triage_run_id: number;
  issue_number: number;
  repo_full_name: string;
  action_type: string;
  payload: Record<string, unknown>;
  risk: "low" | "medium" | "high";
  status: string;
  created_at: string;
}

export interface Overview {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  awaiting_review: number;
  total_cost_usd: number;
  mean_cost_usd: number;
  mean_latency_ms: number;
  pending_actions: number;
  approval_rate_by_type: Record<
    string,
    { approved: number; rejected: number; rate: number | null }
  >;
  classification_distribution: Record<string, number>;
}

export interface LatencyPercentiles {
  p50: number;
  p95: number;
  p99: number;
}

export interface MetricsWindow {
  window: string;
  total_runs: number;
  completed: number;
  failed: number;
  awaiting_review: number;
  success_rate: number;
  mean_cost_usd: number;
  total_cost_usd: number;
  mean_latency_ms: number;
  latency_percentiles: LatencyPercentiles;
  total_tokens: number;
}

export interface ComponentHealth {
  name: string;
  status: "ok" | "degraded" | "down";
  latency_ms?: number;
  detail?: string;
}

export interface HealthStatus {
  status: "ok" | "degraded" | "down";
  components: ComponentHealth[];
  checked_at: string;
}

export interface TraceSpan {
  node: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

export interface RunTrace {
  run_id: number;
  total_latency_ms: number;
  total_cost_usd: number;
  spans: TraceSpan[];
}

export interface DeadLetterItem {
  id: number;
  github_delivery_id: string;
  event_type: string;
  error: string | null;
  received_at: string;
}

export interface DeadLetterResponse {
  count: number;
  items: DeadLetterItem[];
}

export const api = {
  repos: () => get<RepoOut[]>("/api/v1/repos"),
  runs: (cursor?: number) =>
    get<{ items: RunSummary[]; next_cursor: number | null }>(
      `/api/v1/runs${cursor ? `?cursor=${cursor}` : ""}`,
    ),
  run: (id: number) => get<RunDetail>(`/api/v1/runs/${id}`),
  pendingActions: () => get<PendingAction[]>("/api/v1/actions/pending"),
  overview: () => get<Overview>("/api/v1/analytics/overview"),
  observability: {
    metrics: (window = "24h") =>
      get<MetricsWindow>(`/api/v1/observability/metrics?window=${window}`),
    health: () => get<HealthStatus>("/api/v1/observability/health"),
    trace: (runId: number) =>
      get<RunTrace>(`/api/v1/observability/traces/${runId}`),
    deadLetter: () =>
      get<DeadLetterResponse>("/api/v1/observability/dead-letter"),
  },
};
