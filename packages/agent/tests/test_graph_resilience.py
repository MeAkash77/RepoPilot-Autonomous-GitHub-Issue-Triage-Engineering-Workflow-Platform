"""Node-level resilience: enrichment nodes degrade, critical nodes fail hard."""

import pytest

from repopilot_agent.graph import _wrap


async def duplicate_check(state: object, deps: object) -> dict[str, object]:
    raise RuntimeError("provider 429 Too Many Requests")


async def classify(state: object, deps: object) -> dict[str, object]:
    raise RuntimeError("provider 429 Too Many Requests")


async def test_enrichment_node_failure_degrades_with_flag() -> None:
    wrapped = _wrap(duplicate_check, deps=object())
    result = await wrapped(state=object())
    assert result == {"guardrail_flags": ["duplicate_check_unavailable"]}


async def test_critical_node_failure_reraises() -> None:
    wrapped = _wrap(classify, deps=object())
    with pytest.raises(RuntimeError):
        await wrapped(state=object())
