"""LangGraph triage graph.

Topology:
    ingest_sanitize → retrieve_context → classify
        → (duplicate_check ∥ info_gap_check ∥ code_locator)   parallel fan-out
        → assignee_suggester → compose_actions → guardrail_review → END

Bounded by construction: no cycles, no free-running loop. Each node has a
timeout; classification may escalate to the strong model once (handled
inside the node, capped by the per-run cost ceiling).
"""

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph

from repopilot_agent.guardrails.output import guardrail_review
from repopilot_agent.nodes import (
    NodeDeps,
    assignee_suggester,
    classify,
    code_locator,
    compose_actions,
    duplicate_check,
    info_gap_check,
    ingest_sanitize,
    retrieve_context,
)
from repopilot_agent.state import TriageState
from repopilot_llm.router import ChatProvider, LLMRouter

NODE_TIMEOUT_S = 60

MODELS_CONFIG_PATH = Path(__file__).parent / "config" / "models.yaml"

# Critical nodes must succeed — a failure here means we have no trustworthy
# triage and the whole run should fail (and, on the webhook path, be retried
# by arq). Everything else is enrichment: a transient outage (e.g. a free-tier
# rate limit on the per-candidate duplicate_check) degrades that one signal
# rather than discarding an otherwise-good classification.
CRITICAL_NODES = frozenset({"ingest_sanitize", "classify"})

logger = structlog.get_logger()

NodeFn = Callable[[TriageState, NodeDeps], Awaitable[dict[str, object]]]


def make_router(providers: dict[str, ChatProvider]) -> LLMRouter:
    return LLMRouter.from_yaml(MODELS_CONFIG_PATH, providers)


def _wrap(fn: NodeFn, deps: NodeDeps) -> Any:
    name = fn.__name__
    critical = name in CRITICAL_NODES

    async def run(state: TriageState) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(fn(state, deps), timeout=NODE_TIMEOUT_S)
        except Exception as exc:
            if critical:
                raise
            # Enrichment node failed — record it as a flag and continue with
            # this signal empty. The run still produces a classification.
            logger.warning("node.degraded", node=name, error=repr(exc))
            return {"guardrail_flags": [f"{name}_unavailable"]}

    run.__name__ = name
    return run


def build_graph(deps: NodeDeps, checkpointer: object | None = None) -> object:
    graph: StateGraph[TriageState] = StateGraph(TriageState)

    for fn in (
        ingest_sanitize,
        retrieve_context,
        classify,
        duplicate_check,
        info_gap_check,
        code_locator,
        assignee_suggester,
        compose_actions,
    ):
        graph.add_node(fn.__name__, _wrap(fn, deps))
    graph.add_node("guardrail_review", partial(guardrail_review, deps=deps))

    graph.add_edge(START, "ingest_sanitize")
    graph.add_edge("ingest_sanitize", "retrieve_context")
    graph.add_edge("retrieve_context", "classify")
    # parallel fan-out
    graph.add_edge("classify", "duplicate_check")
    graph.add_edge("classify", "info_gap_check")
    graph.add_edge("classify", "code_locator")
    # join: assignee_suggester needs code_locator; LangGraph waits for all
    # incoming branches before running the join node.
    graph.add_edge("duplicate_check", "assignee_suggester")
    graph.add_edge("info_gap_check", "assignee_suggester")
    graph.add_edge("code_locator", "assignee_suggester")
    graph.add_edge("assignee_suggester", "compose_actions")
    graph.add_edge("compose_actions", "guardrail_review")
    graph.add_edge("guardrail_review", END)

    return graph.compile(checkpointer=checkpointer)  # type: ignore[arg-type]


async def run_triage(
    deps: NodeDeps,
    initial_state: TriageState,
    checkpointer: object | None = None,
    thread_id: str | None = None,
) -> TriageState:
    compiled = build_graph(deps, checkpointer)
    config = {"configurable": {"thread_id": thread_id}} if thread_id else None
    result = await compiled.ainvoke(initial_state, config=config)  # type: ignore[attr-defined]
    return TriageState.model_validate(result)
