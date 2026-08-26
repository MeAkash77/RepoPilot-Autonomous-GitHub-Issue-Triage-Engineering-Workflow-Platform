"""Knowledge search endpoint — the hybrid retriever over HTTP.

Used by the MCP server's search_repo_knowledge tool and handy for
debugging retrieval from the dashboard later.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from repopilot_api.deps import DbSession
from repopilot_core.db import Repo
from repopilot_core.settings import get_settings
from repopilot_llm.embeddings import FakeEmbeddingProvider, GeminiEmbeddingProvider
from repopilot_llm.reranker import CohereReranker, FakeReranker
from repopilot_retrieval.search import RetrievedChunk, hybrid_search

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("", response_model=list[RetrievedChunk])
async def search(db: DbSession, repo: str, query: str, k: int = 8) -> list[RetrievedChunk]:
    repo_row = await db.scalar(select(Repo).where(Repo.full_name == repo))
    if repo_row is None:
        raise HTTPException(status_code=404, detail=f"repo {repo!r} not connected")
    settings = get_settings()
    embedder = (
        GeminiEmbeddingProvider()
        if settings.google_api_key.get_secret_value()
        else FakeEmbeddingProvider()
    )
    reranker = CohereReranker() if settings.cohere_api_key.get_secret_value() else FakeReranker()
    return await hybrid_search(db, embedder, reranker, repo_row.id, query, k=min(k, 20))
