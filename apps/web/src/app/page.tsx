"use client";

import { motion } from "framer-motion";
import { Navbar } from "@/components/nav/navbar";
import { Footer } from "@/components/nav/footer";
import { ScrollProgress } from "@/components/micro/scroll-progress";
import { ShaderFieldLazy } from "@/components/webgl/shader-field-lazy";
import { Button } from "@/components/ui/button";
import { Counter } from "@/components/micro/counter";
import { Reveal, Stagger, Marquee } from "@/components/motion";

const EASE = [0.16, 1, 0.3, 1] as const;
const INSTALL_URL = "https://github.com/apps/repopilot-gh/installations/new";

const STACK = [
  "FastAPI",
  "LangGraph",
  "pgvector",
  "Groq",
  "Gemini",
  "Cohere rerank",
  "arq",
  "Langfuse",
  "Next.js",
  "slowapi",
  "OpenTelemetry",
  "Grafana Cloud",
];

const FEATURES = [
  [
    "01",
    "Type & severity, with reasons",
    "Every issue is labelled bug / feature / question / docs and scored 1–4 — each call backed by a short, auditable rationale, not a black-box guess.",
  ],
  [
    "02",
    "Duplicates, with evidence",
    "Hybrid retrieval over your whole issue history finds likely duplicates and quotes the matching lines from both issues, so you confirm in seconds.",
  ],
  [
    "03",
    "Chases missing repro info",
    "Detects when a bug report is missing steps, versions, or logs — and drafts the exact comment that asks for them.",
  ],
  [
    "04",
    "Points at the likely files",
    "Maps the report to the code most likely at fault via retrieval over your source plus path-term matching — a head start before anyone opens the editor.",
  ],
  [
    "05",
    "Suggests an owner",
    "Routes the issue to a maintainer from CODEOWNERS and area history, so nothing sits unassigned.",
  ],
  [
    "06",
    "You approve. It acts.",
    "Every action lands in a review queue. Approve, edit, reject — or raise the autonomy level and let low-risk labels apply themselves.",
  ],
  [
    "07",
    "Secure by design.",
    "Four-layer HTTP defense: per-route rate limits with Retry-After, tenant-scoped data so you only see your own repos, body-size caps, HSTS + CSP on every response, and a per-installation daily abuse budget — all in front of the agent, not bolted on after.",
  ],
  [
    "08",
    "Watch every run.",
    "Live observability dashboard: p50/p95/p99 latency, per-node LLM cost waterfall, system health tiles (DB · Redis · LLM), dead-letter queue, and traces pushed to Grafana Cloud — so you see exactly what happened on every triage, down to the cent.",
  ],
] as const;

const STEPS = [
  [
    "1",
    "Install the GitHub App",
    "Add RepoPilot to a repo or your whole org in two clicks. It reads issues and code, writes labels and comments — nothing more.",
  ],
  [
    "2",
    "It triages every new issue",
    "The moment an issue opens, RepoPilot runs the eight-stage pipeline: classification, duplicates, missing info, owner, and proposed actions.",
  ],
  [
    "3",
    "Review the queue — or automate",
    "Open the dashboard, skim the proposals, approve with a keystroke. Raise the autonomy level to let safe actions run on their own.",
  ],
] as const;

const PIPELINE = [
  "sanitize",
  "retrieve",
  "classify",
  "duplicates",
  "info-gap",
  "locate",
  "assignee",
  "compose",
];

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-xs uppercase tracking-[0.3em] text-lime">
      {children}
    </p>
  );
}

/** Animated EKG sweep — the brand pulse, stretched across the hero. */
function HeroPulse() {
  return (
    <svg
      viewBox="0 0 1200 120"
      preserveAspectRatio="none"
      className="h-24 w-full text-lime"
      aria-hidden
    >
      <motion.path
        d="M0 60 H420 L455 60 L480 18 L510 102 L540 40 L565 60 H760 L788 60 L808 30 L832 88 L856 60 H1200"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 1.8, ease: EASE, delay: 0.3 }}
        style={{
          filter:
            "drop-shadow(0 0 8px color-mix(in srgb, var(--color-lime) 55%, transparent))",
        }}
      />
    </svg>
  );
}

export default function Landing() {
  return (
    <main className="relative overflow-clip bg-bg">
      <ScrollProgress />
      <Navbar />

      {/* Hero */}
      <section className="scanlines relative isolate overflow-hidden border-b border-hairline">
        <ShaderFieldLazy className="opacity-70" />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-bg via-bg/55 to-bg/75" />
        <div className="bg-grid pointer-events-none absolute inset-0 opacity-30" />

        <div className="relative mx-auto max-w-6xl px-6 pt-24 pb-20 md:pt-32">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            <Eyebrow>autonomous issue triage</Eyebrow>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.08 }}
            className="font-display mt-6 max-w-4xl text-5xl font-semibold leading-[0.95] tracking-tight md:text-[5.5rem]"
          >
            Reads every issue.
            <br />
            <span className="text-lime text-glow">Triages</span> in seconds.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.16 }}
            className="mt-7 max-w-xl text-lg leading-relaxed text-ink-dim"
          >
            RepoPilot reads each new GitHub issue the moment it lands —
            classifies it, finds duplicates with cited evidence, asks for
            missing repro info, routes it to an owner — then drops concrete
            actions into a queue you approve. You stop triaging. You start
            shipping.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.24 }}
            className="mt-9 flex flex-wrap items-center gap-3"
          >
            <Button asChild>
              <a href={INSTALL_URL}>Install the GitHub App</a>
            </Button>
            <Button asChild variant="outline">
              <a href="/demo">▶ watch a real triage</a>
            </Button>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.5 }}
            className="mt-16"
          >
            <HeroPulse />
            <div className="mt-4 grid max-w-2xl grid-cols-3 gap-6 font-mono">
              <Metric value={<Counter to={8} />} label="pipeline stages" />
              <Metric
                value={
                  <>
                    <Counter to={3.7} decimals={1} />s
                  </>
                }
                label="mean triage latency"
              />
              <Metric
                value={
                  <>
                    $<Counter to={0.0008} decimals={4} />
                  </>
                }
                label="mean cost / run"
              />
            </div>
          </motion.div>
        </div>
      </section>

      {/* Marquee */}
      <section className="border-b border-hairline bg-bg-2 py-5">
        <Marquee>
          {STACK.map((s) => (
            <span key={s} className="font-mono text-sm text-ink-faint">
              <span className="text-lime-deep">/</span> {s}
            </span>
          ))}
        </Marquee>
      </section>

      {/* Why */}
      <section id="why" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-28">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <Reveal>
            <Eyebrow>the problem</Eyebrow>
            <h2 className="font-display mt-5 text-3xl font-semibold leading-tight tracking-tight md:text-5xl">
              Issues pile up faster than anyone can read them.
            </h2>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="space-y-5 text-lg leading-relaxed text-ink-dim">
              <p>
                Every new issue is a context switch: bug or feature? Duplicate?
                Severe? Who owns it? Does it even have enough to act on?
                Multiply that by a busy repo and triage quietly becomes a second
                job — the one nobody volunteers for.
              </p>
              <p>
                <span className="text-ink">
                  RepoPilot does the reading the instant an issue opens.
                </span>{" "}
                It arrives already classified, deduplicated, owner-routed, and
                attached to concrete next actions — so the human decision is a
                quick yes, not an hour of investigation.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Features */}
      <section
        id="features"
        className="scroll-mt-20 border-y border-hairline bg-bg-2"
      >
        <div className="mx-auto max-w-6xl px-6 py-24">
          <Reveal>
            <Eyebrow>what it does</Eyebrow>
            <h2 className="font-display mt-5 max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">
              Eight jobs it takes off your plate.
            </h2>
          </Reveal>
          <Stagger className="mt-14 grid gap-px overflow-hidden rounded-md border border-hairline bg-hairline sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(([k, t, d]) => (
              <Stagger.Item
                key={k}
                className="group relative bg-panel p-7 transition-colors hover:bg-panel-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-lime-deep">{k}</span>
                  <span className="h-2 w-2 rounded-full bg-hairline-bright transition-all group-hover:bg-lime group-hover:shadow-[0_0_12px] group-hover:shadow-lime" />
                </div>
                <h3 className="font-display mt-5 text-xl font-medium text-ink">
                  {t}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-dim">{d}</p>
              </Stagger.Item>
            ))}
          </Stagger>
        </div>
      </section>

      {/* How */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-28">
        <Reveal>
          <Eyebrow>how to use it</Eyebrow>
          <h2 className="font-display mt-5 max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">
            Live in three steps. No config files.
          </h2>
        </Reveal>
        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {STEPS.map(([n, t, d], i) => (
            <Reveal key={n} delay={i * 0.1}>
              <div className="group relative h-full rounded-md border border-hairline bg-panel p-7 transition-colors hover:border-lime/50">
                <div className="font-display flex h-10 w-10 items-center justify-center rounded-sm border border-lime/40 text-lg text-lime">
                  {n}
                </div>
                <h3 className="font-display mt-6 text-xl font-medium text-ink">
                  {t}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-dim">{d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section
        id="pipeline"
        className="scroll-mt-20 border-y border-hairline bg-bg-2"
      >
        <div className="mx-auto max-w-6xl px-6 py-20">
          <Reveal>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <Eyebrow>under the hood</Eyebrow>
                <h2 className="font-display mt-5 text-2xl font-semibold tracking-tight md:text-3xl">
                  Eight deterministic stages. One bounded graph.
                </h2>
              </div>
              <p className="max-w-sm font-mono text-xs leading-relaxed text-ink-faint">
                No free-running agent loop. Each stage is timed, injection-
                screened, and traced with exact token cost.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="mt-10 flex flex-wrap items-center gap-2 font-mono text-xs">
              {PIPELINE.map((p, i) => (
                <span key={p} className="flex items-center gap-2">
                  <span className="rounded-sm border border-hairline-bright bg-panel px-3 py-1.5 text-ink-dim transition-colors hover:border-lime hover:text-lime">
                    {String(i + 1).padStart(2, "0")} {p}
                  </span>
                  {i < PIPELINE.length - 1 && (
                    <span className="text-lime-deep">›</span>
                  )}
                </span>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="relative mx-auto max-w-6xl px-6 py-28">
        <div className="scanlines relative overflow-hidden rounded-lg border border-hairline bg-panel px-8 py-20 text-center">
          <div className="bg-dots pointer-events-none absolute inset-0 opacity-50" />
          <div className="radial-lime pointer-events-none absolute left-1/2 top-0 h-64 w-64 -translate-x-1/2 opacity-40" />
          <Reveal>
            <h2 className="font-display relative mx-auto max-w-2xl text-3xl font-semibold tracking-tight md:text-5xl">
              See it triage a real issue, start to finish.
            </h2>
            <p className="relative mx-auto mt-5 max-w-md text-ink-dim">
              A captured run on a live repository — every stage, every score,
              every fraction of a cent it cost.
            </p>
            <div className="relative mt-9 flex justify-center">
              <Button asChild>
                <a href="/demo">▶ open the demo</a>
              </Button>
            </div>
          </Reveal>
        </div>
      </section>

      <Footer />
    </main>
  );
}

function Metric({ value, label }: { value: React.ReactNode; label: string }) {
  return (
    <div>
      <div className="text-2xl text-lime">{value}</div>
      <div className="mt-1 text-[11px] uppercase tracking-wider text-ink-faint">
        {label}
      </div>
    </div>
  );
}
