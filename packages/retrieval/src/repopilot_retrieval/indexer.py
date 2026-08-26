"""Repo indexing pipeline: GitHub → documents/chunks with hash gating.

Re-embedding only happens when a document's content hash changes, so the
nightly refresh and webhook-delta paths cost near-zero when nothing moved.
"""

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repopilot_core.db import Chunk, Document, Issue, Repo, SourceType
from repopilot_github.client import GitHubAppClient
from repopilot_llm.embeddings import EmbeddingProvider
from repopilot_retrieval.chunkers import TextChunk, chunk_code, chunk_issue, chunk_markdown

logger = structlog.get_logger()

MAX_CODE_FILES = 200
MAX_FILE_BYTES = 100_000
CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".cs",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".sh",
}
SKIP_PATH_PARTS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".git",
    "__pycache__",
    "migrations",
}
SKIP_FILENAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
    "Cargo.lock",
    "go.sum",
}


@dataclass
class SourceItem:
    source_type: SourceType
    source_ref: str
    title: str
    url: str
    content: str
    metadata: dict[str, Any]
    chunks: list[TextChunk]


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


async def _fetch_issues(
    client: GitHubAppClient, installation_id: int, full_name: str
) -> list[SourceItem]:
    items: list[SourceItem] = []
    page = 1
    while page <= 10:  # cap: 10 pages x 100 = 1000 issues
        batch = await client.request(
            installation_id,
            "GET",
            f"/repos/{full_name}/issues",
            params={"state": "all", "per_page": 100, "page": page},
        )
        if not batch:
            break
        for item in batch:
            body = item.get("body") or ""
            number = item["number"]
            if "pull_request" in item:
                # The issues API includes PRs; index merged ones as PR docs.
                if not item["pull_request"].get("merged_at"):
                    continue
                content = f"{item['title']}\n{body}"
                items.append(
                    SourceItem(
                        source_type=SourceType.PR,
                        source_ref=f"pulls/{number}",
                        title=item["title"],
                        url=item["html_url"],
                        content=content,
                        metadata={"state": item["state"], "number": number},
                        chunks=chunk_issue(number, item["title"], body, "pr", item["state"]),
                    )
                )
            else:
                content = f"{item['title']}\n{body}"
                items.append(
                    SourceItem(
                        source_type=SourceType.ISSUE,
                        source_ref=f"issues/{number}",
                        title=item["title"],
                        url=item["html_url"],
                        content=content,
                        metadata={
                            "state": item["state"],
                            "number": number,
                            "labels": [label["name"] for label in item.get("labels", [])],
                            "author": (item.get("user") or {}).get("login", ""),
                        },
                        chunks=chunk_issue(number, item["title"], body, state=item["state"]),
                    )
                )
        page += 1
    return items


async def _fetch_files(
    client: GitHubAppClient, installation_id: int, full_name: str, default_branch: str
) -> list[SourceItem]:
    tree = await client.request(
        installation_id,
        "GET",
        f"/repos/{full_name}/git/trees/{default_branch}",
        params={"recursive": "1"},
    )
    items: list[SourceItem] = []
    code_count = 0
    for entry in tree.get("tree", []):
        if entry["type"] != "blob" or entry.get("size", 0) > MAX_FILE_BYTES:
            continue
        path: str = entry["path"]
        name = path.rsplit("/", 1)[-1]
        if name in SKIP_FILENAMES or any(part in SKIP_PATH_PARTS for part in path.split("/")):
            continue

        is_readme = name.lower().startswith("readme")
        is_doc = name.endswith(".md") and not is_readme
        is_code = any(name.endswith(ext) for ext in CODE_EXTENSIONS)
        if not (is_readme or is_doc or is_code):
            continue
        if is_code:
            if code_count >= MAX_CODE_FILES:
                continue
            code_count += 1

        try:
            blob = await client.request(
                installation_id, "GET", f"/repos/{full_name}/contents/{path}"
            )
            content = base64.b64decode(blob.get("content", "")).decode("utf-8", errors="replace")
        except Exception:
            logger.warning("indexer.file_fetch_failed", path=path)
            continue
        if not content.strip():
            continue

        if is_readme:
            source_type, chunks = SourceType.README, chunk_markdown(path, content)
        elif is_doc:
            source_type, chunks = SourceType.DOC, chunk_markdown(path, content)
        else:
            source_type, chunks = SourceType.CODE, chunk_code(path, content)
        items.append(
            SourceItem(
                source_type=source_type,
                source_ref=path,
                title=path,
                url=f"https://github.com/{full_name}/blob/{default_branch}/{path}",
                content=content,
                metadata={"path": path},
                chunks=chunks,
            )
        )
    return items


async def _upsert_issue_rows(
    session: AsyncSession, repo: Repo, issue_items: list[SourceItem]
) -> None:
    for item in issue_items:
        if item.source_type != SourceType.ISSUE:
            continue
        number = item.metadata["number"]
        issue = await session.scalar(
            select(Issue).where(Issue.repo_id == repo.id, Issue.github_issue_number == number)
        )
        body = item.content.split("\n", 1)[1] if "\n" in item.content else ""
        if issue is None:
            session.add(
                Issue(
                    repo_id=repo.id,
                    github_issue_number=number,
                    title=item.title,
                    body=body,
                    author_login=item.metadata.get("author", ""),
                    state=item.metadata.get("state", "open"),
                    github_labels=item.metadata.get("labels", []),
                )
            )
        else:
            issue.title = item.title
            issue.body = body
            issue.state = item.metadata.get("state", issue.state)
            issue.github_labels = item.metadata.get("labels", [])


async def index_repo(
    session: AsyncSession,
    client: GitHubAppClient,
    embedder: EmbeddingProvider,
    repo: Repo,
    installation_id: int,
) -> dict[str, int]:
    """Index one repo. Returns counters for logging/metrics."""
    items = await _fetch_issues(client, installation_id, repo.full_name)
    items += await _fetch_files(client, installation_id, repo.full_name, repo.default_branch)
    await _upsert_issue_rows(session, repo, items)

    stats = {"seen": len(items), "embedded": 0, "skipped": 0}
    for item in items:
        content_hash = _hash(item.content)
        document = await session.scalar(
            select(Document).where(
                Document.repo_id == repo.id,
                Document.source_type == item.source_type,
                Document.source_ref == item.source_ref,
            )
        )
        if document is not None and document.content_hash == content_hash:
            stats["skipped"] += 1
            continue

        if document is None:
            document = Document(
                repo_id=repo.id,
                source_type=item.source_type,
                source_ref=item.source_ref,
            )
            session.add(document)
        document.title = item.title
        document.url = item.url
        document.doc_metadata = item.metadata
        document.content_hash = content_hash
        await session.flush()

        # Replace chunks wholesale; hash gating makes this rare.
        for old in await session.scalars(select(Chunk).where(Chunk.document_id == document.id)):
            await session.delete(old)
        embeddings = await embedder.embed([chunk.content for chunk in item.chunks])
        for chunk, embedding in zip(item.chunks, embeddings, strict=True):
            session.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    embedding=embedding,
                )
            )
        stats["embedded"] += 1

    repo.indexed_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    logger.info("indexer.done", repo=repo.full_name, **stats)
    return stats
