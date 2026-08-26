"""Action executor: approved proposed_actions → GitHub API calls.

Risk x autonomy gating (decide_gate) is pure and unit-tested. Execution
is the ONLY place RepoPilot writes to GitHub; nothing else may call
mutating endpoints. close_duplicate is high risk and therefore never
auto-executes regardless of autonomy level.
"""

from datetime import UTC, datetime
from typing import Any, Protocol

import structlog

from repopilot_core.db.models import (
    ActionRisk,
    ActionStatus,
    ActionType,
    AutonomyLevel,
    ProposedAction,
)

logger = structlog.get_logger()

AUTO_EXECUTABLE: dict[AutonomyLevel, set[ActionRisk]] = {
    AutonomyLevel.SUGGEST: set(),
    AutonomyLevel.AUTO_LOW_RISK: {ActionRisk.LOW},
    AutonomyLevel.FULL_AUTO: {ActionRisk.LOW, ActionRisk.MEDIUM},
}


def decide_gate(autonomy: AutonomyLevel, risk: ActionRisk) -> bool:
    """True → execute immediately; False → wait for human approval.
    HIGH risk never auto-executes — not even at full_auto."""
    if risk == ActionRisk.HIGH:
        return False
    return risk in AUTO_EXECUTABLE[autonomy]


class GitHubRequester(Protocol):
    async def request(
        self,
        installation_id: int,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any: ...


async def execute_action(
    github: GitHubRequester,
    installation_id: int,
    repo_full_name: str,
    issue_number: int,
    action: ProposedAction,
) -> dict[str, Any]:
    """Execute one action. Raises on API failure; caller records status."""
    base = f"/repos/{repo_full_name}/issues/{issue_number}"
    payload = action.payload

    if action.action_type == ActionType.ADD_LABELS:
        result = await github.request(
            installation_id, "POST", f"{base}/labels", json={"labels": payload["labels"]}
        )
        return {"labels": [label["name"] for label in result]}

    if action.action_type == ActionType.COMMENT:
        result = await github.request(
            installation_id, "POST", f"{base}/comments", json={"body": payload["body"]}
        )
        return {"comment_id": result["id"], "url": result.get("html_url", "")}

    if action.action_type == ActionType.LINK_DUPLICATE:
        body = (
            f"Possible duplicate of #{payload['duplicate_of']} "
            f"(similarity {payload.get('score', 0):.2f}).\n\n"
            f"Evidence: {payload.get('evidence', 'n/a')}"
        )
        result = await github.request(
            installation_id, "POST", f"{base}/comments", json={"body": body}
        )
        return {"comment_id": result["id"]}

    if action.action_type == ActionType.SUGGEST_ASSIGNEE:
        result = await github.request(
            installation_id, "POST", f"{base}/assignees", json={"assignees": [payload["login"]]}
        )
        return {"assignees": [a["login"] for a in result.get("assignees", [])]}

    if action.action_type == ActionType.CLOSE_DUPLICATE:
        await github.request(
            installation_id,
            "POST",
            f"{base}/comments",
            json={"body": f"Closing as duplicate of #{payload['duplicate_of']}."},
        )
        await github.request(
            installation_id,
            "PATCH",
            base,
            json={"state": "closed", "state_reason": "duplicate"},
        )
        return {"closed_as_duplicate_of": payload["duplicate_of"]}

    raise ValueError(f"unexecutable action type: {action.action_type}")


async def execute_and_record(
    github: GitHubRequester,
    installation_id: int,
    repo_full_name: str,
    issue_number: int,
    action: ProposedAction,
    auto: bool,
) -> None:
    """Execute and stamp status/result on the row (caller commits)."""
    try:
        result = await execute_action(github, installation_id, repo_full_name, issue_number, action)
    except Exception as exc:
        action.status = ActionStatus.EXECUTION_FAILED
        action.github_result = {"error": repr(exc)}
        action.executed_at = datetime.now(UTC).replace(tzinfo=None)
        logger.exception("action.execution_failed", action_id=action.id)
        return
    action.status = ActionStatus.AUTO_EXECUTED if auto else ActionStatus.EXECUTED
    action.github_result = result
    action.executed_at = datetime.now(UTC).replace(tzinfo=None)
    logger.info(
        "action.executed",
        action_id=action.id,
        action_type=action.action_type.value,
        auto=auto,
    )
