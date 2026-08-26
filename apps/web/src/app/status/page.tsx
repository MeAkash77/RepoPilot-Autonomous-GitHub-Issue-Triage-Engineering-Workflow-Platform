"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { HealthStatus } from "@/lib/api";

function statusColor(s: string) {
  if (s === "ok") return "#b6ff3c";
  if (s === "degraded") return "#f59e0b";
  return "#ff5c5c";
}

function statusLabel(s: string) {
  if (s === "ok") return "All systems operational";
  if (s === "degraded") return "Partial degradation";
  return "Service disruption";
}

export default function StatusPage() {
  const [data, setData] = useState<HealthStatus | null | undefined>(undefined);

  useEffect(() => {
    // Public proxy path — no auth key needed
    fetch("/api/proxy/observability/health")
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => setData(null));
  }, []);

  return (
    <main className="min-h-screen bg-bg px-6 py-20 font-mono">
      <div className="mx-auto max-w-xl space-y-10">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-lime">
            RepoPilot
          </p>
          <h1 className="mt-4 text-3xl font-semibold text-ink">
            System status
          </h1>
          {data !== undefined && data !== null && (
            <p
              className="mt-2 text-sm"
              style={{ color: statusColor(data.status) }}
            >
              {statusLabel(data.status)}
            </p>
          )}
          {data === null && (
            <p className="mt-2 text-sm text-danger">API unreachable</p>
          )}
          {data === undefined && (
            <p className="mt-2 text-sm text-ink-dim">Checking…</p>
          )}
        </div>

        {data && (
          <div className="space-y-3">
            {data.components.map((c) => (
              <div
                key={c.name}
                className="flex items-center justify-between rounded-lg border border-hairline bg-panel px-5 py-3"
              >
                <div className="flex items-center gap-3">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: statusColor(c.status) }}
                  />
                  <span className="text-sm text-ink capitalize">{c.name}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-ink-faint">
                  {c.latency_ms !== undefined && (
                    <span>{c.latency_ms.toFixed(0)}ms</span>
                  )}
                  <span style={{ color: statusColor(c.status) }}>
                    {c.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        <p className="text-[11px] text-ink-faint">
          Last checked:{" "}
          {data ? new Date(data.checked_at).toLocaleString() : "—"}
        </p>

        <Link
          href="/"
          className="block text-xs text-ink-faint hover:text-lime transition-colors"
        >
          ← back to repopilot
        </Link>
      </div>
    </main>
  );
}
