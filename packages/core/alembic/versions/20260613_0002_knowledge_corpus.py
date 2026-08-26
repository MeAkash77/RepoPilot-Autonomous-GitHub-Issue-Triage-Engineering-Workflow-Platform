"""Knowledge corpus: documents, chunks (vector + tsvector), issues

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "repo_id",
            sa.Integer(),
            sa.ForeignKey("repos.id", name="fk_documents_repo_id_repos"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Enum("issue", "pr", "readme", "doc", "code", name="sourcetype"),
            nullable=False,
        ),
        sa.Column("source_ref", sa.String(512), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("repo_id", "source_type", "source_ref", name="uq_documents_source"),
    )
    op.create_index("ix_documents_repo_id", "documents", ["repo_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", name="fk_chunks_document_id_documents"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    # Generated full-text column + indexes are Postgres-only, raw DDL.
    op.execute(
        "ALTER TABLE chunks ADD COLUMN tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING GIN (tsv)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "repo_id",
            sa.Integer(),
            sa.ForeignKey("repos.id", name="fk_issues_repo_id_repos"),
            nullable=False,
        ),
        sa.Column("github_issue_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_login", sa.String(255), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("github_labels", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("repo_id", "github_issue_number", name="uq_issues_repo_number"),
    )
    op.create_index("ix_issues_repo_id", "issues", ["repo_id"])


def downgrade() -> None:
    op.drop_table("issues")
    op.drop_table("chunks")
    op.drop_table("documents")
    sa.Enum(name="sourcetype").drop(op.get_bind(), checkfirst=True)
