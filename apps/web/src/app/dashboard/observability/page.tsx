"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  ComponentHealth,
  DeadLetterItem,
  DeadLetterResponse,
  HealthStatus,
  MetricsWindow,
} from "@/lib/api";
import { Card, Empty, Skeleton, Stat } from "@/components/ui";

// ── helpers ──────────────────────────────────────────────────────────────────

function statusColor(s: string) {
  if (s === "ok") return "#b6ff3c";
  if (s === "degraded") return "#f59e0b";
  return "#ff5c5c";
}

function fmtPct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

// ── sub-components ───────────────────────────────────────────────────────────

function HealthTiles({ components }: { components: ComponentHealth[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {components.map((c) => (
        <Card key={c.name} className="flex items-center gap-3">
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: statusColor(c.status) }}
          />
          <div className="min-w-0">
            <p className="truncate font-mono text-xs text-ink">{c.name}</p>
            {c.latency_ms != null && (
              <p className="font-mono text-[10px] text-ink-faint">
                {c.latency_ms.toFixed(0)} ms
              </p>
            )}
            {c.detail && (
              <p className="truncate font-mono text-[10px] text-ink-faint">
                {c.detail}
              </p>
            )}
          </div>
          <span
            className="ml-auto font-mono text-[10px] uppercase"
            style={{ color: statusColor(c.status) }}
          >
            {c.status}
          </span>
        </Card>
      ))}
    </div>
  );
}

function DLQList({ items }: { items: DeadLetterItem[] }) {
  if (items.length === 0)
    return (
      <p className="mt-2 text-sm text-ink-dim">
        No failed deliveries in the last 24h.
      </p>
    );
  return (
    <ul className="mt-3 space-y-2">
      {items.slice(0, 5).map((d) => (
        <li
          key={d.id}
          className="rounded border border-hairline bg-surface p-3 font-mono text-xs"
        >
          <div className="flex items-center justify-between">
            <span className="text-danger">{d.event_type}</span>
            <span className="text-ink-faint">
              {new Date(d.received_at).toLocaleString()}
            </span>
          </div>
          {d.error && (
            <p className="mt-1 truncate text-ink-dim">
              {d.error.slice(0, 120)}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

// ── main page ────────────────────────────────────────────────────────────────

export default function ObservabilityPage() {
  const [health, setHealth] = useState<HealthStatus | null | undefined>(
    undefined,
  );
  const [metrics, setMetrics] = useState<MetricsWindow | null | undefined>(
    undefined,
  );
  const [dlq, setDlq] = useState<DeadLetterResponse | null | undefined>(
    undefined,
  );
  const [window24, setWindow24] = useState<"1h" | "6h" | "24h" | "7d">("24h");

  useEffect(() => {
    fetch("/api/proxy/observability/health")
      .then((r) => (r.ok ? r.json() : null))
      .then(setHealth)
      .catch(() => setHealth(null));

    fetch("/api/proxy/observability/dead-letter")
      .then((r) => (r.ok ? r.json() : null))
      .then(setDlq)
      .catch(() => setDlq(null));
  }, []);

  useEffect(() => {
    setMetrics(undefined);
    fetch(`/api/proxy/observability/metrics?window=${window24}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, [window24]);

  const loading =
    health === undefined || metrics === undefined || dlq === undefined;

  if (loading)
    return (
      <div className="fade-up space-y-6">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Observability
        </h1>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    );

  if (health === null && metrics === null)
    return (
      <Empty title="API unreachable" body="Start the backend and refresh." />
    );

  const systemStatus = health?.status ?? "unknown";

  // Build latency chart data from percentiles — guard every field defensively
  const pct = metrics?.latency_percentiles;
  const latencyData = metrics
    ? [
        { label: "p50", ms: pct?.p50 ?? 0 },
        { label: "p95", ms: pct?.p95 ?? 0 },
        { label: "p99", ms: pct?.p99 ?? 0 },
        { label: "mean", ms: metrics?.mean_latency_ms ?? 0 },
      ]
    : [];

  return (
    <div className="fade-up space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Observability
        </h1>
        <span
          className="rounded-full border px-3 py-0.5 font-mono text-xs"
          style={{
            borderColor: statusColor(systemStatus) + "55",
            color: statusColor(systemStatus),
          }}
        >
          {systemStatus}
        </span>
      </div>

      {/* System health tiles */}
      {health && <HealthTiles components={health.components} />}

      {/* SLO stat cards */}
      {metrics && typeof metrics === "object" && "success_rate" in metrics && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Success rate"
            value={fmtPct(metrics.success_rate ?? 0)}
            hint={`${metrics.completed ?? 0}/${metrics.total_runs ?? 0} runs`}
          />
          <Stat
            label="p95 latency"
            value={`${(metrics.latency_percentiles?.p95 ?? 0).toFixed(0)}ms`}
            hint="target < 8000ms"
          />
          <Stat
            label="Mean cost / run"
            value={`$${(metrics.mean_cost_usd ?? 0).toFixed(4)}`}
            hint={`total $${(metrics.total_cost_usd ?? 0).toFixed(4)}`}
          />
          <Stat
            label="Failed (24h)"
            value={String(metrics.failed ?? 0)}
            hint={`${metrics.awaiting_review ?? 0} awaiting review`}
          />
        </div>
      )}

      {/* Window selector + charts */}
      <div className="flex gap-2">
        {(["1h", "6h", "24h", "7d"] as const).map((w) => (
          <button
            key={w}
            onClick={() => setWindow24(w)}
            className={`rounded px-3 py-1 font-mono text-xs transition-colors ${
              window24 === w
                ? "bg-accent/10 text-accent border border-accent/40"
                : "text-ink-dim hover:text-ink border border-transparent"
            }`}
          >
            {w}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Latency percentile chart */}
        <Card>
          <h2 className="text-sm font-medium">Latency percentiles</h2>
          {latencyData.length === 0 ? (
            <p className="mt-4 text-sm text-ink-dim">No data yet.</p>
          ) : (
            <div className="mt-4 h-52">
              <ResponsiveContainer>
                <BarChart data={latencyData}>
                  <CartesianGrid stroke="#242a24" vertical={false} />
                  <XAxis
                    dataKey="label"
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                    unit="ms"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#121512",
                      border: "1px solid #242a24",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    cursor={{ fill: "rgba(182,255,60,0.08)" }}
                  />
                  <Bar dataKey="ms" fill="#b6ff3c" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        {/* Run volume chart */}
        {metrics && (
          <Card>
            <h2 className="text-sm font-medium">Run summary ({window24})</h2>
            <div className="mt-4 h-52">
              <ResponsiveContainer>
                <BarChart
                  data={[
                    { name: "completed", count: metrics.completed },
                    { name: "awaiting", count: metrics.awaiting_review },
                    { name: "failed", count: metrics.failed },
                  ]}
                >
                  <CartesianGrid stroke="#242a24" vertical={false} />
                  <XAxis
                    dataKey="name"
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#121512",
                      border: "1px solid #242a24",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    cursor={{ fill: "rgba(182,255,60,0.08)" }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {[
                      { fill: "#b6ff3c" },
                      { fill: "#f59e0b" },
                      { fill: "#ff5c5c" },
                    ].map((entry, index) => (
                      <Cell key={index} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}
      </div>

      {/* Dead-letter queue */}
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Dead-letter queue (last 24h)</h2>
          {dlq && dlq.count > 0 && (
            <span className="rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 font-mono text-[11px] text-danger">
              {dlq.count} failed
            </span>
          )}
        </div>
        {dlq ? (
          <DLQList items={dlq.items} />
        ) : (
          <p className="mt-2 text-sm text-ink-dim">Unavailable.</p>
        )}
      </Card>
    </div>
  );
}
