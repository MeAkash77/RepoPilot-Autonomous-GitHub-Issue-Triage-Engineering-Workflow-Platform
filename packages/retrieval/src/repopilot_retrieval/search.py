"""Hybrid search: dense (pgvector cosine) + sparse (tsvector) → RRF → rerank.

Every stage's score is preserved on the returned RetrievedChunk so the
dashboard can render the full retrieval waterfall per run.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from repopilot_core.db import SourceType
from repopilot_llm.embeddings import EmbeddingProvider
from repopilot_llm.reranker import Reranker
from repopilot_retrieval.fusion import reciprocal_rank_fusion

DENSE_TOP_N = 40
SPARSE_TOP_N = 40
RERANK_TOP_N = 30


class RetrievedChunk(BaseModel):
    chunk_id: int
    document_id: int
    content: str
    source_type: SourceType
    source_ref: str
    title: str
    url: str
    dense_score: float | None = None  # cosine similarity
    sparse_score: float | None = None  # ts_rank_cd
    rrf_score: float | None = None
    rerank_score: float | None = None


@dataclass
class _Candidate:
    chunk: RetrievedChunk
    dense_rank: int | None = field(default=None)
    sparse_rank: int | None = field(default=None)


_DENSE_SQL = text("""
    SELECT c.id, c.document_id, c.content, d.source_type, d.source_ref, d.title, d.url,
           1 - (c.embedding <=> CAST(:query_embedding AS vector)) AS score
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE d.repo_id = :repo_id
      AND c.embedding IS NOT NULL
      AND (CAST(:source_type AS text) IS NULL
           OR CAST(d.source_type AS text) = CAST(:source_type AS text))
    ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
    LIMIT :limit
""")

_SPARSE_SQL = text("""
    SELECT c.id, c.document_id, c.content, d.source_type, d.source_ref, d.title, d.url,
           ts_rank_cd(c.tsv, websearch_to_tsquery('english', :query)) AS score
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE d.repo_id = :repo_id
      AND c.tsv @@ websearch_to_tsquery('english', :query)
      AND (CAST(:source_type AS text) IS NULL
           OR CAST(d.source_type AS text) = CAST(:source_type AS text))
    ORDER BY score DESC
    LIMIT :limit
""")


def _row_to_chunk(row: object) -> RetrievedChunk:
    r = row  # sqlalchemy Row with named fields
    return RetrievedChunk(
        chunk_id=r.id,  # type: ignore[attr-defined]
        document_id=r.document_id,  # type: ignore[attr-defined]
        content=r.content,  # type: ignore[attr-defined]
        source_type=SourceType(r.source_type),  # type: ignore[attr-defined]
        source_ref=r.source_ref,  # type: ignore[attr-defined]
        title=r.title,  # type: ignore[attr-defined]
        url=r.url,  # type: ignore[attr-defined]
    )


async def hybrid_search(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    reranker: Reranker,
    repo_id: int,
    query: str,
    k: int = 8,
    source_type: SourceType | None = None,
) -> list[RetrievedChunk]:
    query_embedding = (await embedder.embed([query]))[0]
    type_param = source_type.value if source_type else None

    dense_rows = (
        await session.execute(
            _DENSE_SQL,
            {
                "query_embedding": str(query_embedding),
                "repo_id": repo_id,
                "source_type": type_param,
                "limit": DENSE_TOP_N,
            },
        )
    ).all()
    sparse_rows = (
        await session.execute(
            _SPARSE_SQL,
            {"query": query, "repo_id": repo_id, "source_type": type_param, "limit": SPARSE_TOP_N},
        )
    ).all()

    candidates: dict[int, _Candidate] = {}
    for rank, row in enumerate(dense_rows, start=1):
        candidate = candidates.setdefault(row.id, _Candidate(chunk=_row_to_chunk(row)))
        candidate.dense_rank = rank
        candidate.chunk.dense_score = float(row.score)
    for rank, row in enumerate(sparse_rows, start=1):
        candidate = candidates.setdefault(row.id, _Candidate(chunk=_row_to_chunk(row)))
        candidate.sparse_rank = rank
        candidate.chunk.sparse_score = float(row.score)

    fused = reciprocal_rank_fusion(
        [
            [row.id for row in dense_rows],
            [row.id for row in sparse_rows],
        ]
    )
    for chunk_id, rrf_score in fused:
        candidates[chunk_id].chunk.rrf_score = rrf_score

    rerank_pool = [candidates[chunk_id].chunk for chunk_id, _ in fused[:RERANK_TOP_N]]
    if not rerank_pool:
        return []

    reranked = await reranker.rerank(query, [c.content for c in rerank_pool], top_n=k)
    results = []
    for result in reranked:
        chunk = rerank_pool[result.index]
        chunk.rerank_score = result.score
        results.append(chunk)
    return results
