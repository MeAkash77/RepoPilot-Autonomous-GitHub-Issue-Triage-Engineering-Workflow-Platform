import { api, type RunDetail } from "@/lib/api";
import { Card, Empty, StatusDot } from "@/components/ui";
import { LiveNodeTimeline } from "./live";

export const dynamic = "force-dynamic";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let run: RunDetail;
  try {
    run = await api.run(Number(id));
  } catch {
    return (
      <Empty
        title="Run not found"
        body="It may have been deleted, or the API is down."
      />
    );
  }

  const live = run.status === "queued" || run.status === "running";

  return (
    <div className="fade-up space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="font-display text-xl font-semibold tracking-tight">
            Run #{run.id}
          </h1>
          <StatusDot status={run.status} />
        </div>
        <p className="mt-1 text-sm text-ink-dim">
          <span className="font-mono text-xs text-ink-faint">
            {run.repo_full_name}#{run.issue_number}
          </span>{" "}
          {run.issue_title}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="text-sm font-medium">
            Node timeline{" "}
            {live ? (
              <span className="font-mono text-xs text-accent pulse-dot">
                live
              </span>
            ) : null}
          </h2>
          <LiveNodeTimeline
            runId={run.id}
            initialNodes={run.model_routing}
            terminal={!live}
          />
        </Card>

        <div className="space-y-4">
          <Card>
            <h2 className="text-sm font-medium">Classification</h2>
            {run.classification ? (
              <div className="mt-3 space-y-1 text-sm">
                <p>
                  <span className="font-mono text-accent">
                    {run.classification.type}
                  </span>{" "}
                  · severity {run.classification.severity} ·{" "}
                  {Math.round(run.classification.confidence * 100)}% confident
                </p>
                <p className="text-ink-dim">
                  {run.classification.reasoning_summary}
                </p>
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-dim">—</p>
            )}
          </Card>

          <Card>
            <h2 className="text-sm font-medium">Cost</h2>
            <p className="mt-2 font-mono text-lg">${run.cost_usd.toFixed(5)}</p>
            <p className="font-mono text-xs text-ink-faint">
              {run.total_tokens} tokens · {(run.latency_ms / 1000).toFixed(1)}s
            </p>
            {run.langfuse_trace_id ? (
              <a
                className="mt-2 inline-block text-xs text-accent hover:underline"
                href={`https://cloud.langfuse.com/trace/${run.langfuse_trace_id}`}
                target="_blank"
                rel="noreferrer"
              >
                Langfuse trace →
              </a>
            ) : null}
          </Card>

          {run.duplicates.length > 0 ? (
            <Card>
              <h2 className="text-sm font-medium">Duplicates</h2>
              <ul className="mt-2 space-y-2 text-sm text-ink-dim">
                {run.duplicates.map((d) => (
                  <li key={d.issue_number}>
                    <span className="font-mono text-xs text-accent">
                      #{d.issue_number}
                    </span>{" "}
                    score {d.score.toFixed(2)}
                    <p className="text-xs text-ink-faint">{d.evidence}</p>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {run.related_files.length > 0 ? (
            <Card>
              <h2 className="text-sm font-medium">Related files</h2>
              <ul className="mt-2 space-y-1 font-mono text-xs text-ink-dim">
                {run.related_files.map((f) => (
                  <li key={String(f)}>{String(f)}</li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>
      </div>

      {run.error ? (
        <Card className="border-danger/40">
          <h2 className="text-sm font-medium text-danger">Error</h2>
          <pre className="mt-2 overflow-x-auto font-mono text-xs text-ink-dim">
            {run.error}
          </pre>
        </Card>
      ) : null}

      <details className="rounded-lg border border-hairline bg-surface">
        <summary className="cursor-pointer px-5 py-3 text-sm text-ink-dim">
          Final graph state (JSON)
        </summary>
        <pre className="max-h-96 overflow-auto border-t border-hairline px-5 py-4 font-mono text-xs text-ink-dim">
          {JSON.stringify(run.graph_state, null, 2)}
        </pre>
      </details>
    </div>
  );
}
