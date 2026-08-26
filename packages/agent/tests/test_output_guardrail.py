from repopilot_agent.guardrails.output import review_actions
from repopilot_agent.state import (
    AssigneeSuggestion,
    InjectionRisk,
    ProposedActionDraft,
    TriageState,
)


def _state(**overrides: object) -> TriageState:
    defaults: dict[str, object] = {
        "repo_id": 1,
        "repo_full_name": "ayush/demo",
        "issue_number": 10,
        "issue_title": "t",
        "issue_body": "b",
    }
    defaults.update(overrides)
    return TriageState.model_validate(defaults)


def test_unknown_action_type_stripped() -> None:
    state = _state(
        proposed_actions=[
            ProposedActionDraft(action_type="delete_repo", payload={}, risk="low"),
            ProposedActionDraft(action_type="add_labels", payload={"labels": ["bug"]}, risk="low"),
        ]
    )
    approved, flags = review_actions(state)
    assert [a.action_type for a in approved] == ["add_labels"]
    assert any("action_stripped:unknown" in f for f in flags)


def test_invalid_labels_filtered() -> None:
    state = _state(
        proposed_actions=[
            ProposedActionDraft(
                action_type="add_labels",
                payload={"labels": ["bug", "EVIL<script>", "x" * 99]},
                risk="low",
            )
        ]
    )
    approved, _ = review_actions(state)
    assert approved[0].payload["labels"] == ["bug"]


def test_comment_with_external_url_blocked() -> None:
    state = _state(
        proposed_actions=[
            ProposedActionDraft(
                action_type="comment",
                payload={"body": "Please see https://phishing.example/steal for details"},
                risk="medium",
            )
        ]
    )
    approved, flags = review_actions(state)
    assert approved == []
    assert "comment_blocked:external_url" in flags


def test_comment_with_repo_url_allowed() -> None:
    state = _state(
        proposed_actions=[
            ProposedActionDraft(
                action_type="comment",
                payload={"body": "Related: https://github.com/ayush/demo/issues/5"},
                risk="medium",
            )
        ]
    )
    approved, _ = review_actions(state)
    assert len(approved) == 1


def test_comment_mentions_stripped() -> None:
    state = _state(
        proposed_actions=[
            ProposedActionDraft(
                action_type="comment", payload={"body": "cc @someone please fix"}, risk="medium"
            )
        ]
    )
    approved, flags = review_actions(state)
    assert "@someone" not in approved[0].payload["body"]
    assert "comment_mentions_stripped" in flags


def test_comment_with_secret_pattern_blocked() -> None:
    state = _state(
        proposed_actions=[
            ProposedActionDraft(
                action_type="comment",
                payload={"body": "my token is ghp_abcdefghijklmnopqrstuvwxyz123456"},
                risk="medium",
            )
        ]
    )
    approved, flags = review_actions(state)
    assert approved == []
    assert "comment_blocked:secret_pattern" in flags


def test_close_duplicate_always_high_risk() -> None:
    state = _state(
        proposed_actions=[
            ProposedActionDraft(
                action_type="close_duplicate", payload={"duplicate_of": 5}, risk="low"
            )
        ]
    )
    approved, _ = review_actions(state)
    assert approved[0].risk == "high"


def test_unexpected_assignee_stripped() -> None:
    state = _state(
        assignee_suggestions=[AssigneeSuggestion(login="alice", reason="codeowner", score=1.0)],
        proposed_actions=[
            ProposedActionDraft(
                action_type="suggest_assignee", payload={"login": "mallory"}, risk="low"
            ),
            ProposedActionDraft(
                action_type="suggest_assignee", payload={"login": "alice"}, risk="low"
            ),
        ],
    )
    approved, flags = review_actions(state)
    assert [a.payload["login"] for a in approved] == ["alice"]
    assert "action_stripped:unexpected_assignee" in flags


def test_high_injection_risk_blocks_comments_keeps_labels() -> None:
    state = _state(
        injection_risk=InjectionRisk.HIGH,
        proposed_actions=[
            ProposedActionDraft(action_type="add_labels", payload={"labels": ["bug"]}, risk="low"),
            ProposedActionDraft(action_type="comment", payload={"body": "hello"}, risk="medium"),
        ],
    )
    approved, flags = review_actions(state)
    assert [a.action_type for a in approved] == ["add_labels"]
    assert "comment_blocked:injection_risk" in flags
