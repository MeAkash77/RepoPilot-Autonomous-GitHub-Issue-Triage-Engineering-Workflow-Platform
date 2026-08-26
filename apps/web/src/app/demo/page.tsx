"use client";

// The triage demo, three ways: a motion-graphic intro, an interactive graph of
// the real pipeline you can scrub and inspect, and a screen recording of the
// live dashboard. Everything replays a REAL captured run (lib/demo-data.ts) —
// no backend, loads instantly.

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { DEMO } from "@/lib/demo-data";
import { PipelineGraph } from "@/components/demo/pipeline-graph";
import { Counter } from "@/components/micro/counter";
import { cn } from "@/lib/cn";

const STEP_MS = 1150;
const EASE = [0.16, 1, 0.3, 1] as const;

function usePlayer(count: number) {
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(true);
  useEffect(() => {
    if (!playing || active >= count) return;
    const t = setTimeout(() => setActive((a) => a + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [playing, active, count]);
  const done = active >= count;
  const restart = useCallback(() => {
    setActive(0);
    setPlaying(true);
  }, []);
  const toggle = useCallback(
    () => (done ? restart() : setPlaying((p) => !p)),
    [done, restart],
  );
  return { active, playing, done, setActive, toggle, restart };
}

const RISK: Record<string, string> = {
  low: "text-lime border-lime/40",
  medium: "text-amber border-amber/40",
  high: "text-red border-red/40",
};

export default function DemoPage() {
  const stages = DEMO.stages;
  const { active, playing, done, toggle, restart } = usePlayer(stages.length);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  // Default selection tracks the running stage until the user picks one.
  const runningKey = stages[Math.min(active, stages.length - 1)]?.key ?? null;
  const focusKey = selectedKey ?? runningKey;
  const focus = stages.find((s) => s.key === focusKey);

  const completed = stages.slice(0, active);
  const tokens = completed.reduce(
    (n, s) => n + (s.inputTokens ?? 0) + (s.outputTokens ?? 0),
    0,
  );
  const cost = completed.reduce((c, s) => c + (s.costUsd ?? 0), 0);

  return (
    <main className="min-h-screen bg-bg">
      {/* bar */}
      <div className="sticky top-0 z-40 border-b border-hairline bg-bg/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link
            href="/"
            className="font-mono text-sm text-ink-dim transition-colors hover:text-lime"
          >
            <span className="text-lime">◀</span> back
          </Link>
          <span className="hidden font-mono text-sm text-ink-faint sm:block">
            triage replay · {DEMO.repo}
            <span className="text-lime"> #{DEMO.issueNumber}</span>
          </span>
          <div className="flex items-center gap-2 font-mono text-sm">
            <button
              onClick={toggle}
              className="rounded-sm border border-hairline-bright bg-panel px-4 py-2 text-ink transition-colors hover:border-lime hover:text-lime"
            >
              {done ? "↻ replay" : playing ? "❚❚ pause" : "▶ play"}
            </button>
            <button
              onClick={restart}
              className="rounded-sm border border-hairline-bright bg-panel px-4 py-2 text-ink-dim transition-colors hover:text-ink"
            >
              restart
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* motion-graphic intro */}
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="font-mono text-xs uppercase tracking-[0.3em] text-lime"
        >
          live triage replay
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.05 }}
          className="font-display mt-3 text-3xl font-semibold tracking-tight md:text-5xl"
        >
          One issue. Eight stages.{" "}
          <span className="text-lime">
            <Counter to={DEMO.totals.latencyMs / 1000} decimals={1} />s
          </span>
          .
        </motion.h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-dim">
          A real run captured on a live repository. Watch it flow through the
          graph, then click any stage to inspect exactly what the agent produced
          — every token and cent is what it actually reported.
        </p>

        {/* issue → graph */}
        <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_2fr]">
          {/* input issue */}
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
            className="overflow-hidden rounded-md border border-hairline bg-panel"
          >
            <div className="border-b border-hairline px-4 py-2.5 font-mono text-xs text-ink-faint">
              ▸ input · issue
            </div>
            <div className="p-5">
              <h2 className="font-display text-lg font-medium leading-snug">
                {DEMO.title}
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-ink-dim">
                {DEMO.body}
              </p>
              <p className="mt-4 font-mono text-xs text-ink-faint">
                opened by {DEMO.author}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-px border-t border-hairline bg-hairline">
              <Stat label="tokens" value={tokens.toString()} />
              <Stat label="cost" value={`$${cost.toFixed(5)}`} />
              <Stat label="stage" value={`${active}/${stages.length}`} />
            </div>
          </motion.div>

          {/* graph */}
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, ease: EASE, delay: 0.15 }}
          >
            <PipelineGraph
              active={active}
              selectedKey={selectedKey}
              onSelect={setSelectedKey}
            />
            <p className="mt-2 text-center font-mono text-xs text-ink-faint">
              click a node to inspect its output · {focus?.name}
            </p>
          </motion.div>
        </div>

        {/* detail panel */}
        <div className="mt-5">
          <AnimatePresence mode="wait">
            {focus && (
              <motion.div
                key={focus.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.3, ease: EASE }}
                className="overflow-hidden rounded-md border border-hairline bg-panel"
              >
                <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
                  <span className="font-mono text-xs text-lime-deep">
                    ▸ {focus.name.toLowerCase()}
                  </span>
                  {focus.model && (
                    <span className="font-mono text-xs text-ink-faint">
                      {focus.model} · {focus.inputTokens}→{focus.outputTokens}{" "}
                      tok · ${focus.costUsd?.toFixed(5)} · {focus.latencyMs}ms
                    </span>
                  )}
                </div>
                <div className="p-5">
                  <Detail stageKey={focus.key} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* the real dashboard, recorded */}
        <div className="mt-16">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-lime">
            and where it all lands
          </p>
          <h2 className="font-display mt-3 text-2xl font-semibold tracking-tight md:text-3xl">
            The review dashboard — recorded live.
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-dim">
            Proposed actions queue here for a human yes/no. This is the real
            app, not a mockup — overview, runs, the per-run pipeline, analytics,
            and autonomy controls.
          </p>
          <div className="mt-6 overflow-hidden rounded-lg border border-hairline bg-panel">
            <div className="flex items-center gap-2 border-b border-hairline px-4 py-2.5">
              <span className="flex gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-red" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber" />
                <span className="h-2.5 w-2.5 rounded-full bg-lime" />
              </span>
              <span className="ml-2 font-mono text-[11px] text-ink-faint">
                repopilot — dashboard · screen recording
              </span>
            </div>
            <video
              src="/demo/dashboard.webm"
              autoPlay
              muted
              loop
              playsInline
              className="block w-full"
              suppressHydrationWarning
            />
          </div>
        </div>
      </div>
    </main>
  );
}

function Detail({ stageKey }: { stageKey: string }) {
  if (stageKey === "classify") {
    return (
      <>
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <span className="rounded-sm border border-lime/40 px-2 py-0.5 text-lime">
            {DEMO.classification.type}
          </span>
          <span className="text-ink-dim">
            severity {DEMO.classification.severity} ·{" "}
            {DEMO.classification.severityLabel}
          </span>
          <span className="text-ink-dim">
            {Math.round(DEMO.classification.confidence * 100)}% confident
          </span>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-ink-dim">
          {DEMO.classification.reasoning}
        </p>
      </>
    );
  }
  if (stageKey === "info-gap") {
    return (
      <>
        <ul className="flex flex-wrap gap-2 font-mono text-xs">
          {DEMO.missingInfo.map((m) => (
            <li
              key={m}
              className="rounded-sm border border-amber/40 px-2 py-0.5 text-amber"
            >
              {m}
            </li>
          ))}
        </ul>
        <p className="mt-3 border-l-2 border-lime/40 bg-bg/40 px-3 py-2 text-sm italic leading-relaxed text-ink-dim">
          “{DEMO.draftedComment}”
        </p>
      </>
    );
  }
  if (stageKey === "compose") {
    return (
      <ul className="space-y-2">
        {DEMO.actions.map((a) => (
          <li
            key={a.type}
            className="flex items-center gap-3 rounded-sm border border-hairline bg-bg/40 p-3 font-mono text-xs"
          >
            <span className="text-lime">{a.type}</span>
            <span className={cn("rounded-sm border px-2 py-0.5", RISK[a.risk])}>
              {a.risk}
            </span>
            <span className="text-ink-dim">{a.summary}</span>
          </li>
        ))}
      </ul>
    );
  }
  const stage = DEMO.stages.find((s) => s.key === stageKey)!;
  return (
    <div>
      <p className="text-sm text-ink-dim">{stage.blurb}</p>
      <p className="mt-3 font-mono text-xs text-lime">→ {stage.result}</p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-panel px-4 py-3">
      <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">
        {label}
      </p>
      <p className="mt-1 font-mono text-base text-ink">{value}</p>
    </div>
  );
}
