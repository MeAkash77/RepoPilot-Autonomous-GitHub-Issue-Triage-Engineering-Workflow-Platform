"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { PendingAction } from "@/lib/api";
import { Empty, RiskBadge, SkeletonList } from "@/components/ui";
import { toast } from "@/components/toast";

function payloadSummary(action: PendingAction): string {
  const p = action.payload;
  switch (action.action_type) {
    case "add_labels":
      return `labels: ${(p.labels as string[])?.join(", ")}`;
    case "comment":
      return String(p.body ?? "").slice(0, 200);
    case "link_duplicate":
      return `duplicate of #${p.duplicate_of} (score ${Number(p.score ?? 0).toFixed(2)})`;
    case "suggest_assignee":
      return `assign ${p.login} — ${p.reason}`;
    case "close_duplicate":
      return `close as duplicate of #${p.duplicate_of}`;
    default:
      return JSON.stringify(p);
  }
}

export default function InboxPage() {
  const [actions, setActions] = useState<PendingAction[] | null>(null);
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/proxy/actions/pending");
    if (res.ok) setActions(await res.json());
    else setActions([]);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const review = useCallback(
    async (id: number, verb: "approve" | "reject") => {
      if (busy) return;
      setBusy(true);
      // Optimistic removal; restore on failure.
      const prev = actions ?? [];
      setActions(prev.filter((a) => a.id !== id));
      setSelected((s) => Math.max(0, Math.min(s, prev.length - 2)));
      const res = await fetch(`/api/proxy/actions/${id}/${verb}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ reviewer: "dashboard" }),
      });
      if (!res.ok) {
        setActions(prev);
        toast(`Failed to ${verb} — restored`, "danger");
      } else {
        toast(
          verb === "approve" ? "Approved & executed" : "Rejected",
          verb === "approve" ? "ok" : "info",
        );
      }
      setBusy(false);
    },
    [actions, busy],
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!actions || actions.length === 0) return;
      const current = actions[selected];
      if (e.key === "j" || e.key === "ArrowDown")
        setSelected((s) => Math.min(s + 1, actions.length - 1));
      if (e.key === "k" || e.key === "ArrowUp")
        setSelected((s) => Math.max(s - 1, 0));
      if (e.key === "a" && current) review(current.id, "approve");
      if (e.key === "r" && current) review(current.id, "reject");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [actions, selected, review]);

  if (actions === null)
    return (
      <div className="fade-up space-y-6">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Inbox
        </h1>
        <SkeletonList rows={4} />
      </div>
    );

  return (
    <div className="fade-up space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Inbox
        </h1>
        <p className="font-mono text-xs text-ink-faint">
          j/k navigate · A approve · R reject
        </p>
      </div>

      {actions.length === 0 ? (
        <Empty
          title="Inbox zero"
          body="No actions waiting for review. New triage runs will queue their proposals here."
        />
      ) : (
        <ul className="space-y-2">
          <AnimatePresence initial={false}>
            {actions.map((action, i) => (
              <motion.li
                key={action.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -12, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                onClick={() => setSelected(i)}
                className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                  i === selected
                    ? "border-accent/60 bg-surface-2"
                    : "border-hairline bg-surface hover:border-ink-faint/40"
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="font-mono text-xs text-ink-faint">
                      {action.repo_full_name}#{action.issue_number}
                    </span>
                    <span className="font-mono text-xs text-accent">
                      {action.action_type}
                    </span>
                    <RiskBadge risk={action.risk} />
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        review(action.id, "approve");
                      }}
                      className="rounded-md border border-ok/40 px-2.5 py-1 font-mono text-xs text-ok transition-colors hover:bg-ok/10"
                    >
                      approve
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        review(action.id, "reject");
                      }}
                      className="rounded-md border border-danger/40 px-2.5 py-1 font-mono text-xs text-danger transition-colors hover:bg-danger/10"
                    >
                      reject
                    </button>
                  </div>
                </div>
                <p className="mt-2 truncate text-sm text-ink-dim">
                  {payloadSummary(action)}
                </p>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
