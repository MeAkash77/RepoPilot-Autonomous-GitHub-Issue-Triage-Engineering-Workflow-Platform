import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Shimmer placeholder block. Compose several to mock a loading layout. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} />;
}

/** Stacked skeleton rows for list/table loading states. */
export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2.5">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-hairline bg-surface p-5 ${className}`}
    >
      {children}
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card>
      <p className="text-xs uppercase tracking-widest text-ink-faint">
        {label}
      </p>
      <p className="mt-2 font-mono text-2xl text-ink">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-dim">{hint}</p> : null}
    </Card>
  );
}

const riskTone: Record<string, string> = {
  low: "text-ok border-ok/30 bg-ok/10",
  medium: "text-warn border-warn/30 bg-warn/10",
  high: "text-danger border-danger/30 bg-danger/10",
};

export function RiskBadge({ risk }: { risk: string }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-mono text-[11px] ${riskTone[risk] ?? "border-hairline text-ink-dim"}`}
    >
      {risk}
    </span>
  );
}

const statusTone: Record<string, string> = {
  completed: "text-ok",
  awaiting_review: "text-warn",
  failed: "text-danger",
  running: "text-accent",
  queued: "text-ink-dim",
};

export function StatusDot({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-xs ${statusTone[status] ?? "text-ink-dim"}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full bg-current ${status === "running" ? "pulse-dot" : ""}`}
      />
      {status}
    </span>
  );
}

export function Empty({
  title,
  body,
  children,
}: {
  title: string;
  body: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-hairline px-6 py-16 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-ink-dim">{body}</p>
      {children}
    </div>
  );
}
