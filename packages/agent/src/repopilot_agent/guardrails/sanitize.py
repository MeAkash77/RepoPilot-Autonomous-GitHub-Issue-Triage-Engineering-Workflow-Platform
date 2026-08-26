"""Input-side prompt-injection defense.

Issue bodies are attacker-controlled input feeding an agent that holds
GitHub write permissions. This module strips invisible/steganographic
channels and detects instruction-like patterns. Detection NEVER blocks a
triage run — it downgrades autonomy to suggest-only and flags the UI.
"""

import re

from repopilot_agent.state import InjectionRisk

# Channels invisible to a human reviewer reading the issue on GitHub.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_INVISIBLE_CHARS_RE = re.compile(
    "[​‌‍‎‏⁠⁡⁢⁣⁤﻿­͏\U000e0000-\U000e007f]"  # Unicode tags block — classic smuggling channel
)
_DATA_URI_RE = re.compile(r"data:[^\s)]{32,}")

# Instruction-like patterns addressed to an AI agent. Case-insensitive.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_previous",
        re.compile(
            r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|above|prior|earlier|all)\b.{0,30}\b(instruction|prompt|rule|direction)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "role_reassignment",
        re.compile(
            r"\byou are (now|no longer)\b|\bact as\b.{0,40}\b(admin|root|developer mode|jailbreak|dan)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_probe",
        re.compile(
            r"\b(reveal|show|print|repeat|output)\b.{0,40}\b(system prompt|instructions|your prompt|initial prompt)",
            re.IGNORECASE,
        ),
    ),
    (
        "agent_addressing",
        re.compile(
            r"\b(hey |dear |attention )?(ai|assistant|bot|agent|llm|model)\b.{0,30}\b(must|should|need to|please) (now )?(close|delete|label|apply|approve|execute|post|comment|assign|reveal)",
            re.IGNORECASE,
        ),
    ),
    (
        "direct_tool_command",
        re.compile(
            r"\b(close|delete|merge) (all|every|this) (issue|issues|pr|pull request)s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "new_instructions_block",
        re.compile(
            r"(^|\n)\s*(#+\s*)?(new |updated |real |actual )?(system )?(instructions?|prompt)\s*[:\]]",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_exfiltration",
        re.compile(
            r"\b(send|post|echo|repeat|exfiltrate|forward|leak|include)\b.{0,60}\b(token|secret|key|credential|env|process\.env)",
            re.IGNORECASE,
        ),
    ),
]


def sanitize_issue_body(body: str) -> tuple[str, InjectionRisk, list[str]]:
    """Strip hidden channels, detect injection. Returns
    (sanitized_body, risk, matched_pattern_names)."""
    sanitized = _HTML_COMMENT_RE.sub("", body)
    sanitized = _MD_IMAGE_RE.sub("[image removed]", sanitized)
    sanitized = _INVISIBLE_CHARS_RE.sub("", sanitized)
    sanitized = _DATA_URI_RE.sub("[data-uri removed]", sanitized)

    matches = [name for name, pattern in _INJECTION_PATTERNS if pattern.search(sanitized)]
    # Also scan the ORIGINAL body: instructions hidden in comments/images
    # are the highest-signal attack of all.
    matches += [
        f"hidden:{name}"
        for name, pattern in _INJECTION_PATTERNS
        if pattern.search(body) and not pattern.search(sanitized)
    ]

    hidden_channel_found = bool(_HTML_COMMENT_RE.search(body) or _INVISIBLE_CHARS_RE.search(body))
    # Any instruction-pattern match is HIGH: the agent holds write
    # permissions, so we err loud. A hidden channel alone (comments are
    # common in issue templates) is merely LOW.
    if matches:
        risk = InjectionRisk.HIGH
    elif hidden_channel_found:
        risk = InjectionRisk.LOW
    else:
        risk = InjectionRisk.NONE

    return sanitized.strip(), risk, matches
