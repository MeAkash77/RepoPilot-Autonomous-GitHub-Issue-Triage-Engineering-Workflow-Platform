"""Manual retrieval testing CLI.

    uv run python -m repopilot_retrieval.cli search --repo owner/name --query "..."
    uv run python -m repopilot_retrieval.cli index --repo owner/name

Uses real providers when API keys are configured, fakes otherwise — so
`search` works against locally seeded data without any keys.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from repopilot_core.db import Installation, Repo, get_session_factory
from repopilot_core.settings import get_settings
from repopilot_github.client import GitHubAppClient
from repopilot_llm.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    GeminiEmbeddingProvider,
)
from repopilot_llm.reranker import CohereReranker, FakeReranker, Reranker
from repopilot_retrieval.indexer import index_repo
from repopilot_retrieval.search import hybrid_search


def _embedder() -> EmbeddingProvider:
    if get_settings().google_api_key.get_secret_value():
        return GeminiEmbeddingProvider()
    print("! GOOGLE_API_KEY unset — using FakeEmbeddingProvider", file=sys.stderr)
    return FakeEmbeddingProvider()


def _reranker() -> Reranker:
    if get_settings().cohere_api_key.get_secret_value():
        return CohereReranker()
    print("! COHERE_API_KEY unset — using FakeReranker", file=sys.stderr)
    return FakeReranker()


async def _resolve_repo(full_name: str) -> Repo:
    async with get_session_factory()() as session:
        repo = await session.scalar(select(Repo).where(Repo.full_name == full_name))
    if repo is None:
        print(f"repo {full_name!r} not connected (no row in repos)", file=sys.stderr)
        raise SystemExit(1)
    return repo


async def _search(full_name: str, query: str, k: int) -> None:
    repo = await _resolve_repo(full_name)
    async with get_session_factory()() as session:
        results = await hybrid_search(session, _embedder(), _reranker(), repo.id, query, k=k)
    if not results:
        print("no results")
        return
    for i, chunk in enumerate(results, 1):
        print(
            f"{i}. [{chunk.source_type.value}] {chunk.source_ref}  "
            f"dense={chunk.dense_score if chunk.dense_score is not None else '-'} "
            f"sparse={chunk.sparse_score if chunk.sparse_score is not None else '-'} "
            f"rrf={chunk.rrf_score:.5f} rerank={chunk.rerank_score:.4f}"
            if chunk.rrf_score is not None and chunk.rerank_score is not None
            else f"{i}. [{chunk.source_type.value}] {chunk.source_ref}"
        )
        preview = chunk.content[:160].replace("\n", " ")
        print(f"   {preview}")


async def _index(full_name: str) -> None:
    client = GitHubAppClient()
    async with get_session_factory()() as session:
        repo = await session.scalar(select(Repo).where(Repo.full_name == full_name))
        if repo is None:
            print(f"repo {full_name!r} not connected (no row in repos)", file=sys.stderr)
            raise SystemExit(1)
        installation = await session.get(Installation, repo.installation_id)
        assert installation is not None
        stats = await index_repo(
            session, client, _embedder(), repo, installation.github_installation_id
        )
    print(stats)
    await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="repopilot-retrieval")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="hybrid search over an indexed repo")
    p_search.add_argument("--repo", required=True, help="owner/name")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("-k", type=int, default=8)

    p_index = sub.add_parser("index", help="(re)index a connected repo")
    p_index.add_argument("--repo", required=True, help="owner/name")

    args = parser.parse_args()
    if args.command == "search":
        asyncio.run(_search(args.repo, args.query, args.k))
    else:
        asyncio.run(_index(args.repo))


if __name__ == "__main__":
    main()
