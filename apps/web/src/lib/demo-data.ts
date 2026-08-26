// Captured from a REAL triage run on AyushCoder9/repopilot-sandbox issue #2
// (run id 3). Numbers — tokens, cost, latency — are exactly what the agent
// reported; nothing here is invented. The /demo page replays this so the
// showcase never depends on a live backend or burns an LLM call per view.

export interface DemoStage {
  key: string;
  name: string;
  blurb: string;
  model?: string;
  inputTokens?: number;
  outputTokens?: number;
  costUsd?: number;
  latencyMs?: number;
  /** Short outcome line shown when the stage completes. */
  result: string;
  /** Whether this stage produced a substantive signal vs ran-but-empty. */
  signal: boolean;
}

export interface DemoFixture {
  repo: string;
  issueNumber: number;
  author: string;
  title: string;
  body: string;
  injectionRisk: string;
  classification: {
    type: string;
    severity: number;
    severityLabel: string;
    confidence: number;
    reasoning: string;
  };
  missingInfo: string[];
  draftedComment: string;
  actions: { type: string; risk: string; summary: string }[];
  totals: { tokens: number; costUsd: number; latencyMs: number };
  stages: DemoStage[];
}

export const DEMO: DemoFixture = {
  repo: "AyushCoder9/repopilot-sandbox",
  issueNumber: 2,
  author: "AyushCoder9",
  title: "Large file upload throws an error and breaks the page",
  body: "When I try to upload a big file (mine was around 8MB) the page just breaks and nothing happens. There's some kind of TypeError about 'size' in the console. Small files are fine. Using Chrome on Mac. Can this be fixed?",
  injectionRisk: "none",
  classification: {
    type: "bug",
    severity: 2,
    severityLabel: "major",
    confidence: 0.9,
    reasoning:
      "The issue describes a specific problem with uploading large files, which results in a page break and a TypeError in the console. This behavior is not expected and indicates a broken feature, which aligns with the definition of a 'bug'. The severity is classified as 'major' because the issue prevents the user from uploading large files, but there might be a workaround, such as splitting the file into smaller parts.",
  },
  missingInfo: ["reproduction steps", "version info", "error output / logs"],
  draftedComment:
    "To help with this issue, could you please provide the exact reproduction steps, version info, and the full error output from the console?",
  actions: [
    {
      type: "add_labels",
      risk: "low",
      summary: "Apply labels: bug, severity:major",
    },
    {
      type: "comment",
      risk: "medium",
      summary: "Post a comment requesting the missing repro details",
    },
  ],
  totals: { tokens: 1222, costUsd: 0.00076498, latencyMs: 3668 },
  stages: [
    {
      key: "sanitize",
      name: "Sanitize",
      blurb: "Screen attacker-controlled issue text before any model sees it.",
      result: "No prompt injection detected · risk: none",
      signal: true,
    },
    {
      key: "retrieve",
      name: "Retrieve",
      blurb: "Hybrid RAG over the indexed corpus — dense + sparse, RRF-fused.",
      model: "llama-3.3-70b",
      inputTokens: 166,
      outputTokens: 13,
      costUsd: 0.00010821,
      latencyMs: 2505,
      result: "Condensed query, pulled candidate context",
      signal: true,
    },
    {
      key: "classify",
      name: "Classify",
      blurb: "Assign type + severity with a confidence score and rationale.",
      model: "llama-3.3-70b",
      inputTokens: 487,
      outputTokens: 146,
      costUsd: 0.00040267,
      latencyMs: 614,
      result: "bug · severity major · 90% confident",
      signal: true,
    },
    {
      key: "duplicates",
      name: "Duplicates",
      blurb:
        "Judge each retrieved candidate for a true duplicate, with evidence.",
      result: "No confident duplicate in the corpus",
      signal: false,
    },
    {
      key: "info-gap",
      name: "Info gap",
      blurb: "Detect missing repro details and draft the question to ask.",
      model: "llama-3.3-70b",
      inputTokens: 349,
      outputTokens: 61,
      costUsd: 0.0002541,
      latencyMs: 258,
      result: "3 gaps found · comment drafted",
      signal: true,
    },
    {
      key: "locate",
      name: "Locate",
      blurb: "Map the report to the files most likely at fault.",
      result: "No code chunks above threshold",
      signal: false,
    },
    {
      key: "assignee",
      name: "Assignee",
      blurb: "Suggest an owner from CODEOWNERS and area history.",
      result: "No CODEOWNERS match",
      signal: false,
    },
    {
      key: "compose",
      name: "Compose",
      blurb: "Turn analysis into concrete actions, gated by autonomy level.",
      result: "2 actions composed → approval queue",
      signal: true,
    },
  ],
};
