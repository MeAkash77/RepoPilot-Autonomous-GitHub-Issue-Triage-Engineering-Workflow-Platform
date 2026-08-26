"""Typed LangGraph state for a triage run.

Every node reads from and writes distinct keys of this state, so the
parallel fan-out (duplicate_check / info_gap_check / code_locator) merges
without reducers.
"""

import enum
from typing import Annotated, Any

from pydantic import BaseModel, Field

from repopilot_retrieval.search import RetrievedChunk


class IssueType(enum.StrEnum):
    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"
    DOCS = "docs"


class InjectionRisk(enum.StrEnum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"


class Classification(BaseModel):
    type: IssueType
    severity: int = Field(ge=1, le=4, description="1=critical … 4=trivial")
    confidence: float = Field(ge=0, le=1)
    reasoning_summary: str = Field(max_length=600)


class DuplicateVerdict(BaseModel):
    issue_number: int
    score: float = Field(ge=0, le=1, description="retrieval similarity score")
    verdict: str = Field(description="'duplicate' or 'not_duplicate'")
    evidence: str = Field(default="", max_length=1000)


class MissingInfo(BaseModel):
    missing: list[str] = Field(default_factory=list)  # subset of known element names
    asked_comment: str = ""


class AssigneeSuggestion(BaseModel):
    login: str
    reason: str
    score: float


class ProposedActionDraft(BaseModel):
    action_type: str  # add_labels | comment | link_duplicate | suggest_assignee | close_duplicate
    payload: dict[str, Any]
    risk: str  # low | medium | high


class NodeCost(BaseModel):
    node: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


def _merge_costs(left: list[NodeCost], right: list[NodeCost]) -> list[NodeCost]:
    return left + right


def _merge_flags(left: list[str], right: list[str]) -> list[str]:
    return left + right


class TriageState(BaseModel):
    # inputs
    repo_id: int
    repo_full_name: str
    issue_number: int
    issue_title: str
    issue_body: str
    issue_author: str = ""
    autonomy_level: str = "suggest"

    # ingest_sanitize
    sanitized_body: str = ""
    injection_risk: InjectionRisk = InjectionRisk.NONE

    # retrieve_context
    retrieved_context: list[RetrievedChunk] = Field(default_factory=list)
    condensed_query: str = ""

    # parallel analysis nodes
    classification: Classification | None = None
    duplicates: list[DuplicateVerdict] = Field(default_factory=list)
    missing_info: MissingInfo | None = None
    related_files: list[str] = Field(default_factory=list)

    # downstream
    assignee_suggestions: list[AssigneeSuggestion] = Field(default_factory=list)
    proposed_actions: list[ProposedActionDraft] = Field(default_factory=list)

    # bookkeeping (parallel-safe via reducers)
    guardrail_flags: Annotated[list[str], _merge_flags] = Field(default_factory=list)
    node_costs: Annotated[list[NodeCost], _merge_costs] = Field(default_factory=list)
    escalation_used: bool = False

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.node_costs)

    @property
    def total_tokens(self) -> int:
        return sum(c.input_tokens + c.output_tokens for c in self.node_costs)
