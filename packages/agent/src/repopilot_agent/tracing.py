"""Langfuse tracing, no-op without credentials.

One trace per triage run; node costs become spans attached post-hoc from
the state's node_costs ledger (nodes stay free of tracing imports — they
only append NodeCost records, which keeps them trivially unit-testable).
"""

import uuid
from typing import Any

import structlog

from repopilot_agent.state import TriageState
from repopilot_core.settings import get_settings

logger = structlog.get_logger()


class RunTracer:
    def __init__(self) -> None:
        settings = get_settings()
        self.trace_id: str = uuid.uuid4().hex
        self._client: Any = None
        if settings.langfuse_public_key and settings.langfuse_secret_key.get_secret_value():
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key.get_secret_value(),
                    host=settings.langfuse_host,
                )
            except Exception:
                logger.warning("langfuse.init_failed")

    def record_run(self, state: TriageState, latency_ms: int, error: str | None = None) -> None:
        if self._client is None:
            return
        try:
            trace = self._client.trace(
                id=self.trace_id,
                name="triage_run",
                input={
                    "repo": state.repo_full_name,
                    "issue_number": state.issue_number,
                    "title": state.issue_title,
                },
                output={
                    "classification": state.classification.model_dump()
                    if state.classification
                    else None,
                    "duplicates": [d.model_dump() for d in state.duplicates],
                    "actions": [a.model_dump() for a in state.proposed_actions],
                    "guardrail_flags": state.guardrail_flags,
                    "error": error,
                },
                metadata={
                    "injection_risk": state.injection_risk.value,
                    "total_cost_usd": state.total_cost_usd,
                    "total_tokens": state.total_tokens,
                    "latency_ms": latency_ms,
                },
            )
            for cost in state.node_costs:
                trace.span(
                    name=cost.node,
                    metadata={
                        "model": cost.model,
                        "input_tokens": cost.input_tokens,
                        "output_tokens": cost.output_tokens,
                        "cost_usd": cost.cost_usd,
                        "latency_ms": cost.latency_ms,
                    },
                )
            self._client.flush()
            logger.info("langfuse.recorded", trace_id=self.trace_id)
        except Exception as exc:
            logger.warning("langfuse.record_failed", trace_id=self.trace_id, error=repr(exc))
