"""Triage graph nodes.

Each node is an async function (state, deps) → dict of state updates,
independently unit-testable with fake providers. Cost/latency for every
LLM call is appended to node_costs. Low-confidence classification gets one
escalation retry with the stronger route — at most one per run, enforced
by the escalation_used flag and the per-run cost ceiling.
"""

import time
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repopilot_agent.guardrails.sanitize import sanitize_issue_body
from repopilot_agent.prompts.registry import load_prompt
from repopilot_agent.state import (
    AssigneeSuggestion,
    Classification,
    DuplicateVerdict,
    InjectionRisk,
    MissingInfo,
    NodeCost,
    ProposedActionDraft,
    TriageState,
)
from repopilot_core.db import SourceType
from repopilot_core.settings import get_settings
from repopilot_github.client import GitHubAppClient
from repopilot_llm.embeddings import EmbeddingProvider
from repopilot_llm.reranker import Reranker
from repopilot_llm.router import LLMResponse, LLMRouter
from repopilot_retrieval.search import hybrid_search

logger = structlog.get_logger()

CLASSIFY_CONFIDENCE_FLOOR = 0.6
DUPLICATE_CANDIDATE_THRESHOLD = 0.45  # retrieval-score floor before judging
MAX_DUPLICATE_CANDIDATES = 5
CONTEXT_CHUNKS_FOR_PROMPT = 6


@dataclass
class NodeDeps:
    """Everything nodes need, injected so tests run fully offline."""

    session_factory: async_sessionmaker[AsyncSession]
    router: LLMRouter
    embedder: EmbeddingProvider
    reranker: Reranker
    github: GitHubAppClient | None = None
    installation_id: int | None = None


def _cost(node: str, response: LLMResponse, started: float) -> NodeCost:
    return NodeCost(
        node=node,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        latency_ms=int((time.monotonic() - started) * 1000),
    )


# --- ingest_sanitize -------------------------------------------------------


async def ingest_sanitize(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    sanitized, risk, patterns = sanitize_issue_body(state.issue_body)
    flags = [f"injection:{p}" for p in patterns]
    autonomy = state.autonomy_level
    if risk == InjectionRisk.HIGH and autonomy != "suggest":
        autonomy = "suggest"
        flags.append("autonomy_downgraded_to_suggest")
    return {
        "sanitized_body": sanitized,
        "injection_risk": risk,
        "guardrail_flags": flags,
        "autonomy_level": autonomy,
    }


# --- retrieve_context ------------------------------------------------------


async def retrieve_context(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    started = time.monotonic()
    prompt = load_prompt("condense_query")
    response = await deps.router.complete(
        "condense_query",
        [
            {
                "role": "user",
                "content": prompt.render(title=state.issue_title, body=state.sanitized_body[:4000]),
            }
        ],
    )
    condensed = response.text.strip()[:300]

    async with deps.session_factory() as session:
        raw_results = await hybrid_search(
            session,
            deps.embedder,
            deps.reranker,
            state.repo_id,
            f"{state.issue_title}\n{state.sanitized_body[:1200]}",
            k=8,
        )
        condensed_results = await hybrid_search(
            session, deps.embedder, deps.reranker, state.repo_id, condensed, k=8
        )

    seen: set[int] = set()
    merged = []
    for chunk in raw_results + condensed_results:
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            merged.append(chunk)
    return {
        "retrieved_context": merged[:12],
        "condensed_query": condensed,
        "node_costs": [_cost("retrieve_context", response, started)],
    }


# --- classify ---------------------------------------------------------------


def _context_block(state: TriageState) -> str:
    parts = []
    for chunk in state.retrieved_context[:CONTEXT_CHUNKS_FOR_PROMPT]:
        parts.append(f"--- [{chunk.source_type.value}] {chunk.source_ref}\n{chunk.content[:800]}")
    return "\n".join(parts) if parts else "(no relevant context found)"


async def _classify_once(
    state: TriageState, deps: NodeDeps, route: str
) -> tuple[Classification, LLMResponse]:
    prompt = load_prompt("classify")
    return await deps.router.complete_structured(
        route,
        [
            {
                "role": "system",
                "content": prompt.render(
                    repo_full_name=state.repo_full_name,
                    context=_context_block(state),
                    few_shot="",
                    title=state.issue_title,
                    body=state.sanitized_body[:6000],
                ),
            },
            {"role": "user", "content": "Classify the issue in the <issue_data> block."},
        ],
        schema=Classification,
    )


async def classify(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    started = time.monotonic()
    classification, response = await _classify_once(state, deps, "classify")
    costs = [_cost("classify", response, started)]
    escalated = False

    ceiling = get_settings().max_cost_per_run_usd
    if (
        classification.confidence < CLASSIFY_CONFIDENCE_FLOOR
        and not state.escalation_used
        and state.total_cost_usd + costs[0].cost_usd < ceiling
    ):
        started = time.monotonic()
        classification, response = await _classify_once(state, deps, "escalation")
        costs.append(_cost("classify:escalation", response, started))
        escalated = True
        logger.info("classify.escalated", issue=state.issue_number)

    return {
        "classification": classification,
        "node_costs": costs,
        "escalation_used": state.escalation_used or escalated,
    }


# --- duplicate_check --------------------------------------------------------


class _DuplicateJudgment(BaseModel):
    verdict: str = Field(description="'duplicate' or 'not_duplicate'")
    confidence: float = Field(ge=0, le=1)
    evidence_new: str = Field(default="", description="quote from the new issue")
    evidence_candidate: str = Field(default="", description="quote from the candidate issue")


async def duplicate_check(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    query = f"{state.issue_title}\n{state.sanitized_body[:1200]}"
    async with deps.session_factory() as session:
        candidates = await hybrid_search(
            session,
            deps.embedder,
            deps.reranker,
            state.repo_id,
            query,
            k=MAX_DUPLICATE_CANDIDATES,
            source_type=SourceType.ISSUE,
        )

    prompt = load_prompt("duplicate_check")
    verdicts: list[DuplicateVerdict] = []
    costs: list[NodeCost] = []
    for candidate in candidates:
        score = candidate.rerank_score or 0.0
        # Skip self-matches and weak candidates.
        number = _issue_number_from_ref(candidate.source_ref)
        if number is None or number == state.issue_number:
            continue
        if score < DUPLICATE_CANDIDATE_THRESHOLD:
            continue
        started = time.monotonic()
        judgment, response = await deps.router.complete_structured(
            "duplicate_check",
            [
                {
                    "role": "system",
                    "content": prompt.render(
                        repo_full_name=state.repo_full_name,
                        title=state.issue_title,
                        body=state.sanitized_body[:4000],
                        candidate_number=str(number),
                        candidate_content=candidate.content[:4000],
                    ),
                },
                {"role": "user", "content": "Judge whether these are duplicates."},
            ],
            schema=_DuplicateJudgment,
        )
        costs.append(_cost("duplicate_check", response, started))
        if (
            judgment.verdict == "duplicate"
            and judgment.evidence_new
            and judgment.evidence_candidate
        ):
            verdicts.append(
                DuplicateVerdict(
                    issue_number=number,
                    score=score,
                    verdict="duplicate",
                    evidence=f"new: {judgment.evidence_new!r} / existing: {judgment.evidence_candidate!r}",
                )
            )
    return {"duplicates": verdicts, "node_costs": costs}


def _issue_number_from_ref(ref: str) -> int | None:
    if not ref.startswith("issues/"):
        return None
    try:
        return int(ref.split("/", 1)[1])
    except ValueError:
        return None


# --- info_gap_check ---------------------------------------------------------


async def info_gap_check(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    if state.classification is None or state.classification.type.value != "bug":
        return {"missing_info": MissingInfo()}
    started = time.monotonic()
    prompt = load_prompt("info_gap")
    missing, response = await deps.router.complete_structured(
        "info_gap",
        [
            {
                "role": "system",
                "content": prompt.render(title=state.issue_title, body=state.sanitized_body[:6000]),
            },
            {"role": "user", "content": "Identify genuinely missing information."},
        ],
        schema=MissingInfo,
    )
    return {"missing_info": missing, "node_costs": [_cost("info_gap_check", response, started)]}


# --- code_locator ------------------------------------------------------------


async def code_locator(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    """Retrieval over code chunks + path-name term matching. No LLM."""
    query = f"{state.issue_title}\n{state.condensed_query}"
    async with deps.session_factory() as session:
        code_chunks = await hybrid_search(
            session,
            deps.embedder,
            deps.reranker,
            state.repo_id,
            query,
            k=10,
            source_type=SourceType.CODE,
        )
    scores: dict[str, float] = {}
    for chunk in code_chunks:
        scores[chunk.source_ref] = max(scores.get(chunk.source_ref, 0.0), chunk.rerank_score or 0.0)
    # Path-name heuristic: issue text mentioning a path component boosts it.
    text = f"{state.issue_title} {state.sanitized_body}".lower()
    for path in scores:
        stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
        if len(stem) >= 4 and stem in text:
            scores[path] += 0.5
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    return {"related_files": [path for path, _ in ranked[:5]]}


# --- assignee_suggester -------------------------------------------------------


async def assignee_suggester(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    """CODEOWNERS + commit frequency on related files. Deliberately LLM-free."""
    if deps.github is None or deps.installation_id is None or not state.related_files:
        return {"assignee_suggestions": []}

    suggestions: dict[str, AssigneeSuggestion] = {}
    codeowners = await _fetch_codeowners(deps, state.repo_full_name)
    for path in state.related_files:
        for owner in _codeowners_for_path(codeowners, path):
            entry = suggestions.setdefault(
                owner, AssigneeSuggestion(login=owner, reason="CODEOWNERS match", score=0.0)
            )
            entry.score += 1.0

    for path in state.related_files[:3]:
        try:
            commits = await deps.github.request(
                deps.installation_id,
                "GET",
                f"/repos/{state.repo_full_name}/commits",
                params={"path": path, "per_page": 30},
            )
        except Exception:
            logger.warning("assignee.commit_fetch_failed", path=path)
            continue
        for commit in commits or []:
            author = (commit.get("author") or {}).get("login")
            if author and not author.endswith("[bot]"):
                entry = suggestions.setdefault(
                    author,
                    AssigneeSuggestion(login=author, reason="frequent committer", score=0.0),
                )
                entry.score += 0.2

    ranked = sorted(suggestions.values(), key=lambda s: -s.score)[:3]
    return {"assignee_suggestions": ranked}


async def _fetch_codeowners(deps: NodeDeps, full_name: str) -> list[tuple[str, list[str]]]:
    assert deps.github is not None and deps.installation_id is not None
    import base64

    for location in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        try:
            blob = await deps.github.request(
                deps.installation_id, "GET", f"/repos/{full_name}/contents/{location}"
            )
        except Exception:
            continue
        text = base64.b64decode(blob.get("content", "")).decode("utf-8", errors="replace")
        rules = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            owners = [p.lstrip("@") for p in parts[1:] if p.startswith("@") and "/" not in p]
            if owners:
                rules.append((parts[0], owners))
        return rules
    return []


def _codeowners_for_path(rules: list[tuple[str, list[str]]], path: str) -> list[str]:
    """Last matching rule wins, per CODEOWNERS semantics. Glob support is
    intentionally minimal: prefix and extension patterns cover the bulk."""
    matched: list[str] = []
    for pattern, owners in rules:
        cleaned = pattern.lstrip("/")
        if (
            pattern == "*"
            or path == cleaned
            or path.startswith(cleaned.rstrip("*").rstrip("/") + "/")
            or (pattern.startswith("*.") and path.endswith(pattern[1:]))
        ):
            matched = owners
    return matched


# --- compose_actions (deterministic) -----------------------------------------


TYPE_LABELS = {
    "bug": "bug",
    "feature": "enhancement",
    "question": "question",
    "docs": "documentation",
}
SEVERITY_LABELS = {
    1: "severity:critical",
    2: "severity:major",
    3: "severity:minor",
    4: "severity:trivial",
}


async def compose_actions(state: TriageState, deps: NodeDeps) -> dict[str, object]:
    actions: list[ProposedActionDraft] = []
    if state.classification is not None:
        labels = [TYPE_LABELS[state.classification.type.value]]
        if state.classification.type.value == "bug":
            labels.append(SEVERITY_LABELS[state.classification.severity])
        actions.append(
            ProposedActionDraft(
                action_type="add_labels",
                payload={"labels": labels, "reasoning": state.classification.reasoning_summary},
                risk="low",
            )
        )
    if state.missing_info and state.missing_info.missing and state.missing_info.asked_comment:
        actions.append(
            ProposedActionDraft(
                action_type="comment",
                payload={
                    "body": state.missing_info.asked_comment,
                    "missing": state.missing_info.missing,
                },
                risk="medium",
            )
        )
    for duplicate in state.duplicates:
        actions.append(
            ProposedActionDraft(
                action_type="link_duplicate",
                payload={
                    "duplicate_of": duplicate.issue_number,
                    "score": duplicate.score,
                    "evidence": duplicate.evidence,
                },
                risk="medium",
            )
        )
    for suggestion in state.assignee_suggestions[:1]:
        actions.append(
            ProposedActionDraft(
                action_type="suggest_assignee",
                payload={"login": suggestion.login, "reason": suggestion.reason},
                risk="low",
            )
        )
    return {"proposed_actions": actions}
