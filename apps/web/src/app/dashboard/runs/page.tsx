import Link from "next/link";
import { api } from "@/lib/api";
import { Empty, StatusDot } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  let runs;
  try {
    runs = (await api.runs()).items;
  } catch {
    return (
      <Empty title="API unreachable" body="Start the backend and refresh." />
    );
  }

  return (
    <div className="fade-up space-y-6">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Triage runs
      </h1>
      {runs.length === 0 ? (
        <Empty
          title="No runs yet"
          body="Open an issue on a connected repo, or run the triage CLI, and the run will appear here."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-hairline">
          <table className="w-full text-sm">
            <thead className="bg-surface text-left font-mono text-[11px] uppercase tracking-wider text-ink-faint">
              <tr>
                <th className="px-4 py-2.5">run</th>
                <th className="px-4 py-2.5">issue</th>
                <th className="px-4 py-2.5">status</th>
                <th className="px-4 py-2.5 text-right">cost</th>
                <th className="px-4 py-2.5 text-right">tokens</th>
                <th className="px-4 py-2.5 text-right">latency</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  className="border-t border-hairline transition-colors hover:bg-surface"
                >
                  <td className="px-4 py-2.5 font-mono text-xs">
                    <Link
                      href={`/dashboard/runs/${run.id}`}
                      className="text-accent hover:underline"
                    >
                      #{run.id}
                    </Link>
                  </td>
                  <td className="max-w-xs truncate px-4 py-2.5">
                    <span className="font-mono text-xs text-ink-faint">
                      {run.repo_full_name}#{run.issue_number}
                    </span>{" "}
                    {run.issue_title}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusDot status={run.status} />
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">
                    ${run.cost_usd.toFixed(4)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">
                    {run.total_tokens}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">
                    {(run.latency_ms / 1000).toFixed(1)}s
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
