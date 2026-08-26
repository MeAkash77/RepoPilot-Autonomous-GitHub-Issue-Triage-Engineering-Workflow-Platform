# Evals

Prompts are code: any change under `packages/agent/**`, `packages/retrieval/**`, or `packages/llm/**` triggers the eval workflow, and regressions block the merge.

## Run locally

```bash
uv run python -m repopilot_evals.runner --suite all
uv run python -m repopilot_evals.runner --suite redteam        # deterministic, no keys needed
uv run python -m repopilot_evals.runner --update-baseline      # refresh committed baseline (main only)
```

## Suites & gates

| Suite | What it measures | Needs | Gate |
| --- | --- | --- | --- |
| red-team | 25 adversarial issues + 1 benign control vs the layered injection defense | nothing (deterministic) | **100% pass, hard** |
| classification | accuracy + macro-F1 of the classify node on the labeled dataset | `GROQ_API_KEY` | macro-F1 drop ≤ 2pts vs baseline |
| retrieval | recall@k over labeled queries (building blocks in `retrieval_metrics.py`) | Postgres | informational (gate lands with the labeled query set) |

The red-team suite is additionally wired into pytest (`evals/tests/test_redteam_gate.py`), so plain `uv run pytest` fails on any defense regression — the gate cannot be skipped by not running the eval CLI.

## Red-team design (and its honest limits)

Each case simulates the **worst case**: the model is assumed fully compromised by the attacker text. The harness feeds attacker-shaped action drafts (comment echoing the raw issue body, label bombing, attacker-named assignee, low-risk close, non-allowlisted action) through the real defense code:

1. **Input layer** — `sanitize_issue_body`: strips HTML comments, markdown images, invisible Unicode (including the U+E0000 tags block), data URIs; flags instruction patterns; any flag ⇒ injection risk HIGH ⇒ autonomy forced to suggest-only.
2. **Output layer** — `review_actions`: strict action allowlist; comments blocked on external URLs, secret patterns, hidden channels; @-mentions stripped; label charset/length/count caps; assignees must come from the deterministic suggester; `close_duplicate` forced HIGH risk (never auto-executed).

This is deliberately **not** an LLM-in-the-loop eval: it verifies the *deterministic* security boundary that holds even when the LLM is fully fooled. The benign control case (rt-026) must pass *through* unblocked, guarding against the trivial "block everything" fix.

## Dataset growth

- `harvest.py` pulls closed issues from public OSS repos into `evals/datasets/harvested/` with suggested labels for human confirmation (target: 120+ labeled cases).
- Every maintainer approve/reject/edit is stored in `feedback_events` and exported as candidate eval cases.

## Duplicate-detection threshold

The retrieval-score floor for judging candidates (`DUPLICATE_CANDIDATE_THRESHOLD = 0.45`) plus the judge's mandatory two-sided evidence quote form the operating point. The ROC sweep to calibrate the threshold against labeled duplicate pairs is the planned analysis once the harvested dataset is labeled; until then the floor is conservative (favoring precision) and `link_duplicate` is medium-risk so a human reviews every link in suggest mode.
