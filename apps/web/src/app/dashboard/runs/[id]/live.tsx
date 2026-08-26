"use client";

// SSE-driven node timeline. For finished runs it renders the recorded
// node costs; for live runs it subscribes to /runs/{id}/stream and grows
// as nodes complete.

import { useEffect, useState } from "react";
import type { NodeCost } from "@/lib/api";

export function LiveNodeTimeline({
  runId,
  initialNodes,
  terminal,
}: {
  runId: number;
  initialNodes: NodeCost[];
  terminal: boolean;
}) {
  const [nodes, setNodes] = useState<NodeCost[]>(initialNodes);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (terminal) return;
    const source = new EventSource(`/api/proxy/runs/${runId}/stream`);
    source.addEventListener("node", (e) => {
      setNodes((prev) => [...prev, JSON.parse((e as MessageEvent).data)]);
    });
    source.addEventListener("status", (e) => {
      setStatus(JSON.parse((e as MessageEvent).data).status);
    });
    source.addEventListener("done", () => source.close());
    source.addEventListener("error", () => source.close());
    return () => source.close();
  }, [runId, terminal]);

  if (nodes.length === 0) {
    return (
      <p className="mt-4 font-mono text-sm text-ink-dim">
        {terminal
          ? "no LLM nodes recorded"
          : `waiting for first node… (${status ?? "queued"})`}
      </p>
    );
  }

  const maxLatency = Math.max(...nodes.map((n) => n.latency_ms), 1);

  return (
    <ol className="mt-4 space-y-2.5">
      {nodes.map((node, i) => (
        <li key={`${node.node}-${i}`} className="fade-up">
          <div className="flex items-baseline justify-between font-mono text-xs">
            <span className="text-ink">{node.node}</span>
            <span className="text-ink-faint">
              {node.model} · {node.input_tokens}→{node.output_tokens} tok · $
              {node.cost_usd.toFixed(5)} · {node.latency_ms}ms
            </span>
          </div>
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-accent/70"
              style={{ width: `${(node.latency_ms / maxLatency) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ol>
  );
}
