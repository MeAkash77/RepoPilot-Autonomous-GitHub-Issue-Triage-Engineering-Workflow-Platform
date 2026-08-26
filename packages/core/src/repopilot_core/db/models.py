"""Core tables: installations/repos, knowledge corpus, triage pipeline.

JSON columns use the generic JSON type with a JSONB variant so unit tests
can run on SQLite while production uses Postgres JSONB. The chunks.tsv
generated tsvector column and the HNSW/GIN indexes are Postgres-only and
live exclusively in migrations — hybrid search queries them with raw SQL.
"""

import enum
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from repopilot_core.db.base import Base, CreatedAtMixin

EMBEDDING_DIM = 1024

JsonDict = dict[str, Any]
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class AutonomyLevel(enum.StrEnum):
    SUGGEST = "suggest"
    AUTO_LOW_RISK = "auto_low_risk"
    FULL_AUTO = "full_auto"


class WebhookDeliveryStatus(enum.StrEnum):
    RECEIVED = "received"
    ENQUEUED = "enqueued"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"
    THROTTLED = "throttled"


class Installation(Base, CreatedAtMixin):
    __tablename__ = "installations"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_installation_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    account_login: Mapped[str] = mapped_column(String(255))

    repos: Mapped[list["Repo"]] = relationship(back_populates="installation")


class Repo(Base, CreatedAtMixin):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    installation_id: Mapped[int] = mapped_column(ForeignKey("installations.id"))
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    autonomy_level: Mapped[AutonomyLevel] = mapped_column(
        Enum(AutonomyLevel, values_callable=lambda e: [m.value for m in e]),
        default=AutonomyLevel.SUGGEST,
    )
    settings: Mapped[JsonDict] = mapped_column(JSONVariant, default=dict)
    indexed_at: Mapped[datetime | None] = mapped_column(default=None)

    installation: Mapped[Installation] = relationship(back_populates="repos")


class WebhookDelivery(Base):
    """Idempotency ledger: one row per GitHub delivery, keyed by X-GitHub-Delivery."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (Index("ix_webhook_deliveries_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    github_delivery_id: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[JsonDict] = mapped_column(JSONVariant)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        Enum(WebhookDeliveryStatus, values_callable=lambda e: [m.value for m in e]),
        default=WebhookDeliveryStatus.RECEIVED,
    )
    error: Mapped[str | None] = mapped_column(Text, default=None)
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TriageRunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionType(enum.StrEnum):
    ADD_LABELS = "add_labels"
    COMMENT = "comment"
    LINK_DUPLICATE = "link_duplicate"
    SUGGEST_ASSIGNEE = "suggest_assignee"
    CLOSE_DUPLICATE = "close_duplicate"


class ActionRisk(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXECUTION_FAILED = "execution_failed"
    AUTO_EXECUTED = "auto_executed"


class FeedbackVerdict(enum.StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class SourceType(enum.StrEnum):
    ISSUE = "issue"
    PR = "pr"
    README = "readme"
    DOC = "doc"
    CODE = "code"


class Document(Base):
    """One indexed source artifact (an issue, a doc file, a source file)."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("repo_id", "source_type", "source_ref", name="uq_documents_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"), index=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, values_callable=lambda e: [m.value for m in e])
    )
    source_ref: Mapped[str] = mapped_column(String(512))  # 'issues/123', 'src/auth/jwt.py'
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    doc_metadata: Mapped[JsonDict] = mapped_column("metadata", JSONVariant, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """Embedded retrieval unit. The tsv generated column exists only in
    Postgres (added by migration); it is intentionally unmapped."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any] = mapped_column(
        Vector(EMBEDDING_DIM),  # type: ignore[no-untyped-call]
        nullable=True,
    )

    document: Mapped[Document] = relationship(back_populates="chunks")


class Issue(Base, CreatedAtMixin):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("repo_id", "github_issue_number", name="uq_issues_repo_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"), index=True)
    github_issue_number: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    author_login: Mapped[str] = mapped_column(String(255), default="")
    state: Mapped[str] = mapped_column(String(20), default="open")
    github_labels: Mapped[list[Any]] = mapped_column(JSONVariant, default=list)

    triage_runs: Mapped[list["TriageRun"]] = relationship(back_populates="issue")


class TriageRun(Base, CreatedAtMixin):
    __tablename__ = "triage_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    status: Mapped[TriageRunStatus] = mapped_column(
        Enum(TriageRunStatus, values_callable=lambda e: [m.value for m in e]),
        default=TriageRunStatus.QUEUED,
        index=True,
    )
    graph_state: Mapped[JsonDict | None] = mapped_column(JSONVariant, default=None)
    classification: Mapped[JsonDict | None] = mapped_column(JSONVariant, default=None)
    duplicates: Mapped[list[Any]] = mapped_column(JSONVariant, default=list)
    missing_info: Mapped[JsonDict | None] = mapped_column(JSONVariant, default=None)
    related_files: Mapped[list[Any]] = mapped_column(JSONVariant, default=list)
    suggested_assignees: Mapped[list[Any]] = mapped_column(JSONVariant, default=list)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(64), default=None)
    total_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    model_routing: Mapped[list[Any]] = mapped_column(JSONVariant, default=list)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)

    issue: Mapped[Issue] = relationship(back_populates="triage_runs")
    actions: Mapped[list["ProposedAction"]] = relationship(back_populates="triage_run")


class ProposedAction(Base, CreatedAtMixin):
    __tablename__ = "proposed_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    triage_run_id: Mapped[int] = mapped_column(ForeignKey("triage_runs.id"), index=True)
    action_type: Mapped[ActionType] = mapped_column(
        Enum(ActionType, values_callable=lambda e: [m.value for m in e])
    )
    payload: Mapped[JsonDict] = mapped_column(JSONVariant, default=dict)
    risk: Mapped[ActionRisk] = mapped_column(
        Enum(ActionRisk, values_callable=lambda e: [m.value for m in e])
    )
    status: Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus, values_callable=lambda e: [m.value for m in e]),
        default=ActionStatus.PENDING,
        index=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    executed_at: Mapped[datetime | None] = mapped_column(default=None)
    github_result: Mapped[JsonDict | None] = mapped_column(JSONVariant, default=None)

    triage_run: Mapped[TriageRun] = relationship(back_populates="actions")
    feedback: Mapped[list["FeedbackEvent"]] = relationship(back_populates="proposed_action")


class FeedbackEvent(Base, CreatedAtMixin):
    """Every reviewer decision, kept as labeled data for future evals."""

    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposed_action_id: Mapped[int] = mapped_column(ForeignKey("proposed_actions.id"), index=True)
    verdict: Mapped[FeedbackVerdict] = mapped_column(
        Enum(FeedbackVerdict, values_callable=lambda e: [m.value for m in e])
    )
    edited_payload: Mapped[JsonDict | None] = mapped_column(JSONVariant, default=None)
    reviewer: Mapped[str] = mapped_column(String(255), default="")

    proposed_action: Mapped[ProposedAction] = relationship(back_populates="feedback")
