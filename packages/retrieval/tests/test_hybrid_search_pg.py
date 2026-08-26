"""Integration test for hybrid search against real Postgres+pgvector.

Skipped automatically when Postgres is unreachable (e.g. laptop without
docker compose up). CI provides a pgvector service container.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from repopilot_core.db import Chunk, Document, Installation, Repo, SourceType
from repopilot_llm.embeddings import FakeEmbeddingProvider
from repopilot_llm.reranker import FakeReranker
from repopilot_retrieval.search import hybrid_search

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://repopilot:repopilot@localhost:5432/repopilot"
)


async def _postgres_available() -> bool:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect():
            return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    if not await _postgres_available():
        pytest.skip("postgres not reachable")
    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture
async def seeded_repo(session: AsyncSession) -> Repo:
    """Installation + repo + three documents with embedded chunks.
    Everything rolls back after the test."""
    suffix = uuid.uuid4().hex[:8]
    installation = Installation(
        github_installation_id=int(suffix, 16), account_login=f"test-{suffix}"
    )
    session.add(installation)
    await session.flush()
    repo = Repo(
        installation_id=installation.id,
        github_repo_id=int(suffix, 16) + 1,
        full_name=f"test/{suffix}",
        default_branch="main",
    )
    session.add(repo)
    await session.flush()

    embedder = FakeEmbeddingProvider()
    corpus = [
        (SourceType.ISSUE, "issues/1", "Login crash", "[ISSUE #1] app crashes on login button"),
        (
            SourceType.ISSUE,
            "issues/2",
            "Docs typo",
            "[ISSUE #2] typo in readme installation section",
        ),
        (
            SourceType.CODE,
            "src/auth.py",
            "src/auth.py",
            "[CODE src/auth.py] def login(): token validation logic",
        ),
    ]
    for source_type, ref, title, content in corpus:
        document = Document(
            repo_id=repo.id,
            source_type=source_type,
            source_ref=ref,
            title=title,
            url=f"https://github.com/test/{suffix}",
            content_hash=ref,
        )
        session.add(document)
        await session.flush()
        [embedding] = await embedder.embed([content])
        session.add(
            Chunk(document_id=document.id, chunk_index=0, content=content, embedding=embedding)
        )
    await session.flush()
    return repo


async def test_hybrid_search_returns_relevant_chunk_first(
    session: AsyncSession, seeded_repo: Repo
) -> None:
    results = await hybrid_search(
        session,
        FakeEmbeddingProvider(),
        FakeReranker(),
        seeded_repo.id,
        "app crashes on login",
        k=3,
    )
    assert results
    assert results[0].source_ref == "issues/1"
    # Waterfall scores present
    assert results[0].rrf_score is not None
    assert results[0].rerank_score is not None


async def test_source_type_filter(session: AsyncSession, seeded_repo: Repo) -> None:
    results = await hybrid_search(
        session,
        FakeEmbeddingProvider(),
        FakeReranker(),
        seeded_repo.id,
        "login token validation",
        k=3,
        source_type=SourceType.CODE,
    )
    assert results
    assert all(r.source_type == SourceType.CODE for r in results)


async def test_no_results_for_unknown_repo(session: AsyncSession, seeded_repo: Repo) -> None:
    results = await hybrid_search(
        session, FakeEmbeddingProvider(), FakeReranker(), repo_id=999999, query="anything", k=3
    )
    assert results == []
