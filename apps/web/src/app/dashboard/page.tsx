import Link from "next/link";
import { api, type Overview } from "@/lib/api";
import { Card, Empty, Stat } from "@/components/ui";

export const dynamic = "force-dynamic";

async function load(): Promise<Overview | null> {
  try {
    return await api.overview();
  } catch {
    return null;
  }
}

export default async function OverviewPage() {
  const data = await load();
  if (!data) {
    return (
      <Empty
        title="API unreachable"
        body="Start the backend (uvicorn repopilot_api.main:app) and refresh."
      />
    );
  }
  const distribution = Object.entries(data.classification_distribution);
  const distTotal = distribution.reduce((sum, [, n]) => sum + n, 0) || 1;

  return (
    <div className="fade-up space-y-8">
      <div className="flex items-end justify-between">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Overview
        </h1>
        {data.pending_actions > 0 ? (
          <Link
            href="/dashboard/inbox"
            className="rounded-md bg-accent px-3 py-1.5 text-sm text-black transition-colors hover:bg-accent-dim"
          >
            {data.pending_actions} pending action
            {data.pending_actions === 1 ? "" : "s"} →
          </Link>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Triage runs" value={String(data.total_runs)} />
        <Stat
          label="Awaiting review"
          value={String(data.awaiting_review)}
          hint={`${data.failed_runs} failed`}
        />
        <Stat
          label="Mean cost / run"
          value={`$${data.mean_cost_usd.toFixed(4)}`}
          hint={`$${data.total_cost_usd.toFixed(2)} total`}
        />
        <Stat
          label="Mean latency"
          value={`${(data.mean_latency_ms / 1000).toFixed(1)}s`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-medium text-ink">Classification mix</h2>
          {distribution.length === 0 ? (
            <p className="mt-4 text-sm text-ink-dim">No classified runs yet.</p>
          ) : (
            <div className="mt-4 space-y-3">
              {distribution.map(([label, count]) => (
                <div key={label}>
                  <div className="flex justify-between font-mono text-xs text-ink-dim">
                    <span>{label}</span>
                    <span>{count}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full rounded-full bg-accent"
                      style={{ width: `${(count / distTotal) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <h2 className="text-sm font-medium text-ink">
            Approval rate by action
            <span className="ml-2 text-xs font-normal text-ink-faint">
              live precision proxy
            </span>
          </h2>
          {Object.keys(data.approval_rate_by_type).length === 0 ? (
            <p className="mt-4 text-sm text-ink-dim">
              No reviewed actions yet — approvals will appear here.
            </p>
          ) : (
            <table className="mt-4 w-full text-sm">
              <tbody>
                {Object.entries(data.approval_rate_by_type).map(
                  ([type, stats]) => (
                    <tr key={type} className="border-t border-hairline">
                      <td className="py-2 font-mono text-xs text-ink-dim">
                        {type}
                      </td>
                      <td className="py-2 text-right font-mono text-xs">
                        {stats.rate === null
                          ? "—"
                          : `${Math.round(stats.rate * 100)}%`}
                      </td>
                      <td className="py-2 pl-4 text-right font-mono text-[11px] text-ink-faint">
                        {stats.approved}✓ {stats.rejected}✗
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
