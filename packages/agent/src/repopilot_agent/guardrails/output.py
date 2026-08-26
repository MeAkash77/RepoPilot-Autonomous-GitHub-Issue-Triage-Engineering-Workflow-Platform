"""Output-side guardrail: strict action allowlist + comment screening.

Runs as the final graph node before persistence. Anything not matching
the allowlist schema is stripped, never "fixed". Posted text is screened
for external URLs, @-mentions, and secret-looking strings — the last line
of defense if injected instructions survived every earlier layer.
"""

import re

from repopilot_agent.state import InjectionRisk, ProposedActionDraft, TriageState

ALLOWED_ACTIONS = {"add_labels", "comment", "link_duplicate", "suggest_assignee", "close_duplicate"}
ALLOWED_RISKS = {"low", "medium", "high"}
MAX_COMMENT_LENGTH = 1500
MAX_LABELS = 5

_ALLOWED_LABEL_RE = re.compile(r"^[a-z0-9:_\- ]{1,50}$")
_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<![\w/])@([\w-]+)")
_SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}"
    r"|AKIA[A-Z0-9]{16}|xox[bpars]-[A-Za-z0-9-]{10,})"
)
_HIDDEN_CHANNEL_RE = re.compile(r"<!--|data:[^\s)]{32,}|[\U000e0000-\U000e007f]")


def _screen_comment(body: str, repo_full_name: str) -> tuple[str | None, list[str]]:
    """Returns (safe_body | None, flags). None = comment blocked."""
    flags = []
    if len(body) > MAX_COMMENT_LENGTH:
        body = body[:MAX_COMMENT_LENGTH]
        flags.append("comment_truncated")
    if _SECRET_RE.search(body):
        return None, ["comment_blocked:secret_pattern"]
    if _HIDDEN_CHANNEL_RE.search(body):
        return None, ["comment_blocked:hidden_channel"]
    for url in _URL_RE.findall(body):
        if f"github.com/{repo_full_name}" not in url:
            return None, ["comment_blocked:external_url"]
    if _MENTION_RE.search(body):
        body = _MENTION_RE.sub(lambda m: m.group(1), body)
        flags.append("comment_mentions_stripped")
    return body, flags


def review_actions(state: TriageState) -> tuple[list[ProposedActionDraft], list[str]]:
    """Validate every drafted action against the allowlist. Returns
    (surviving actions, guardrail flags)."""
    approved: list[ProposedActionDraft] = []
    flags: list[str] = []
    suggested_assignees = {s.login for s in state.assignee_suggestions}

    for action in state.proposed_actions:
        if action.action_type not in ALLOWED_ACTIONS or action.risk not in ALLOWED_RISKS:
            flags.append(f"action_stripped:unknown:{action.action_type}")
            continue

        if action.action_type == "add_labels":
            labels = [
                label
                for label in action.payload.get("labels", [])[:MAX_LABELS]
                if isinstance(label, str) and _ALLOWED_LABEL_RE.match(label)
            ]
            if not labels:
                flags.append("action_stripped:no_valid_labels")
                continue
            action.payload["labels"] = labels

        elif action.action_type == "comment":
            body = action.payload.get("body", "")
            if not isinstance(body, str) or not body.strip():
                flags.append("action_stripped:empty_comment")
                continue
            safe_body, comment_flags = _screen_comment(body, state.repo_full_name)
            flags.extend(comment_flags)
            if safe_body is None:
                continue
            action.payload["body"] = safe_body

        elif action.action_type in ("link_duplicate", "close_duplicate"):
            if not isinstance(action.payload.get("duplicate_of"), int):
                flags.append("action_stripped:bad_duplicate_ref")
                continue
            if action.action_type == "close_duplicate":
                action.risk = "high"  # never auto-executed, no exceptions

        elif action.action_type == "suggest_assignee" and (
            action.payload.get("login") not in suggested_assignees
        ):
            flags.append("action_stripped:unexpected_assignee")
            continue

        approved.append(action)

    if state.injection_risk == InjectionRisk.HIGH:
        # High injection risk: posting attacker-influenced text is the one
        # thing we refuse outright; labels/links remain (human-approved).
        kept = [a for a in approved if a.action_type != "comment"]
        if len(kept) != len(approved):
            flags.append("comment_blocked:injection_risk")
        approved = kept

    return approved, flags


async def guardrail_review(state: TriageState, deps: object) -> dict[str, object]:
    approved, flags = review_actions(state)
    return {"proposed_actions": approved, "guardrail_flags": flags}
