"""Phase 1 tables: installations, repos, webhook_deliveries

Revision ID: 0001
Revises:
Create Date: 2026-06-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("github_installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "github_installation_id", name="uq_installations_github_installation_id"
        ),
    )

    op.create_table(
        "repos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "installation_id",
            sa.Integer(),
            sa.ForeignKey("installations.id", name="fk_repos_installation_id_installations"),
            nullable=False,
        ),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False),
        sa.Column(
            "autonomy_level",
            sa.Enum("suggest", "auto_low_risk", "full_auto", name="autonomylevel"),
            nullable=False,
        ),
        sa.Column("settings", JSONB(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("github_repo_id", name="uq_repos_github_repo_id"),
    )
    op.create_index("ix_repos_full_name", "repos", ["full_name"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("github_delivery_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "received",
                "enqueued",
                "processed",
                "failed",
                "skipped",
                name="webhookdeliverystatus",
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("github_delivery_id", name="uq_webhook_deliveries_github_delivery_id"),
    )
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("repos")
    op.drop_table("installations")
    sa.Enum(name="autonomylevel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="webhookdeliverystatus").drop(op.get_bind(), checkfirst=True)
