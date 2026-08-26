from typing import Any

import pytest

from repopilot_core.db.models import (
    ActionRisk,
    ActionStatus,
    ActionType,
    AutonomyLevel,
    ProposedAction,
)
from repopilot_github.executor import decide_gate, execute_action, execute_and_record


@pytest.mark.parametrize(
    ("autonomy", "risk", "expected"),
    [
        (AutonomyLevel.SUGGEST, ActionRisk.LOW, False),
        (AutonomyLevel.SUGGEST, ActionRisk.MEDIUM, False),
        (AutonomyLevel.SUGGEST, ActionRisk.HIGH, False),
        (AutonomyLevel.AUTO_LOW_RISK, ActionRisk.LOW, True),
        (AutonomyLevel.AUTO_LOW_RISK, ActionRisk.MEDIUM, False),
        (AutonomyLevel.AUTO_LOW_RISK, ActionRisk.HIGH, False),
        (AutonomyLevel.FULL_AUTO, ActionRisk.LOW, True),
        (AutonomyLevel.FULL_AUTO, ActionRisk.MEDIUM, True),
        (AutonomyLevel.FULL_AUTO, ActionRisk.HIGH, False),  # never
    ],
)
def test_gate_matrix(autonomy: AutonomyLevel, risk: ActionRisk, expected: bool) -> None:
    assert decide_gate(autonomy, risk) is expected


class FakeGitHub:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.fail = fail

    async def request(
        self,
        installation_id: int,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((method, path, json))
        if self.fail:
            raise RuntimeError("boom")
        if path.endswith("/labels"):
            return [{"name": label} for label in (json or {}).get("labels", [])]
        if path.endswith("/comments"):
            return {"id": 123, "html_url": "https://github.com/x"}
        if path.endswith("/assignees"):
            return {"assignees": [{"login": (json or {})["assignees"][0]}]}
        return {}


def _action(action_type: ActionType, payload: dict[str, Any]) -> ProposedAction:
    return ProposedAction(
        id=1, triage_run_id=1, action_type=action_type, payload=payload, risk=ActionRisk.LOW
    )


async def test_add_labels_calls_github() -> None:
    github = FakeGitHub()
    result = await execute_action(
        github, 1, "a/b", 7, _action(ActionType.ADD_LABELS, {"labels": ["bug"]})
    )
    assert result == {"labels": ["bug"]}
    assert github.calls[0][1] == "/repos/a/b/issues/7/labels"


async def test_close_duplicate_comments_then_closes() -> None:
    github = FakeGitHub()
    await execute_action(
        github, 1, "a/b", 7, _action(ActionType.CLOSE_DUPLICATE, {"duplicate_of": 3})
    )
    methods_paths = [(m, p) for m, p, _ in github.calls]
    assert methods_paths == [
        ("POST", "/repos/a/b/issues/7/comments"),
        ("PATCH", "/repos/a/b/issues/7"),
    ]
    assert github.calls[1][2] == {"state": "closed", "state_reason": "duplicate"}


async def test_execute_and_record_marks_failure_without_raising() -> None:
    action = _action(ActionType.COMMENT, {"body": "hi"})
    await execute_and_record(FakeGitHub(fail=True), 1, "a/b", 7, action, auto=True)
    assert action.status == ActionStatus.EXECUTION_FAILED
    assert "boom" in (action.github_result or {}).get("error", "")


async def test_execute_and_record_auto_vs_manual_status() -> None:
    auto_action = _action(ActionType.COMMENT, {"body": "hi"})
    await execute_and_record(FakeGitHub(), 1, "a/b", 7, auto_action, auto=True)
    assert auto_action.status == ActionStatus.AUTO_EXECUTED

    manual = _action(ActionType.COMMENT, {"body": "hi"})
    await execute_and_record(FakeGitHub(), 1, "a/b", 7, manual, auto=False)
    assert manual.status == ActionStatus.EXECUTED
