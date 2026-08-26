"use client";

// Interactive pipeline graph (React Flow) wired in RepoPilot's real LangGraph
// topology: sanitize → retrieve → classify → {duplicates ∥ info-gap ∥ locate}
// → assignee → compose. Nodes light up as the run progresses; click any node
// to inspect its real captured output. Themed to the phosphor system.

import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import { useMemo } from "react";
import { DEMO, type DemoStage } from "@/lib/demo-data";
import { cn } from "@/lib/cn";

type StageState = "done" | "running" | "pending";
type StageData = { stage: DemoStage; state: StageState; selected: boolean };

const POS: Record<string, { x: number; y: number }> = {
  sanitize: { x: 0, y: 140 },
  retrieve: { x: 195, y: 140 },
  classify: { x: 390, y: 140 },
  duplicates: { x: 610, y: 20 },
  "info-gap": { x: 610, y: 140 },
  locate: { x: 610, y: 260 },
  assignee: { x: 830, y: 140 },
  compose: { x: 1025, y: 140 },
};

const EDGES: [string, string][] = [
  ["sanitize", "retrieve"],
  ["retrieve", "classify"],
  ["classify", "duplicates"],
  ["classify", "info-gap"],
  ["classify", "locate"],
  ["duplicates", "assignee"],
  ["info-gap", "assignee"],
  ["locate", "assignee"],
  ["assignee", "compose"],
];

function StageNode({ data }: NodeProps<Node<StageData>>) {
  const { stage, state, selected } = data;
  return (
    <div
      className={cn(
        "w-[150px] rounded-md border bg-panel px-3 py-2.5 transition-all",
        state === "running" && "border-lime shadow-[0_0_18px_-2px] shadow-lime",
        state === "done" &&
          (stage.signal ? "border-lime/50" : "border-hairline-bright"),
        state === "pending" && "border-hairline opacity-45",
        selected && "ring-1 ring-lime",
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0 !bg-hairline-bright"
      />
      <div className="flex items-center justify-between">
        <span className="font-display text-sm font-medium text-ink">
          {stage.name}
        </span>
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            state === "running"
              ? "bg-lime pulse-dot"
              : state === "done"
                ? stage.signal
                  ? "bg-lime"
                  : "bg-ink-faint"
                : "bg-hairline-bright",
          )}
        />
      </div>
      <p className="mt-1 font-mono text-[11px] leading-tight text-ink-faint">
        {state === "done"
          ? stage.signal
            ? "signal"
            : "no signal"
          : state === "running"
            ? "running…"
            : "queued"}
      </p>
      <Handle
        type="source"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0 !bg-hairline-bright"
      />
    </div>
  );
}

const nodeTypes = { stage: StageNode };

export function PipelineGraph({
  active,
  selectedKey,
  onSelect,
}: {
  active: number;
  selectedKey: string | null;
  onSelect: (key: string) => void;
}) {
  const stageIndex = useMemo(
    () => Object.fromEntries(DEMO.stages.map((s, i) => [s.key, i])),
    [],
  );

  const nodes: Node<StageData>[] = useMemo(
    () =>
      DEMO.stages.map((stage, i) => ({
        id: stage.key,
        type: "stage",
        position: POS[stage.key],
        draggable: false,
        data: {
          stage,
          state: i < active ? "done" : i === active ? "running" : "pending",
          selected: selectedKey === stage.key,
        },
      })),
    [active, selectedKey],
  );

  const edges: Edge[] = useMemo(
    () =>
      EDGES.map(([s, t]) => {
        const lit = stageIndex[s] < active;
        return {
          id: `${s}-${t}`,
          source: s,
          target: t,
          animated: lit,
          style: {
            stroke: lit ? "var(--color-lime)" : "var(--color-hairline-bright)",
            strokeWidth: lit ? 1.5 : 1,
            opacity: lit ? 0.9 : 0.4,
          },
        };
      }),
    [active, stageIndex],
  );

  return (
    <div className="h-[400px] w-full overflow-hidden rounded-md border border-hairline bg-bg-2">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, n) => onSelect(n.id)}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        panOnScroll={false}
        zoomOnScroll={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={26}
          size={1}
          color="var(--color-hairline)"
        />
      </ReactFlow>
    </div>
  );
}
