"""Cross-encoder reranker abstraction.

Production uses Cohere Rerank (free trial tier); the fake scores by token
overlap so retrieval tests are deterministic and offline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from repopilot_core.settings import get_settings

COHERE_RERANK_URL = "https://api.cohere.com/v2/rerank"


@dataclass
class RerankResult:
    index: int  # position in the input documents list
    score: float


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankResult]:
        """Return top_n results sorted by descending relevance score."""


class CohereReranker(Reranker):
    def __init__(self, model: str = "rerank-v3.5") -> None:
        self._model = model
        self._api_key = get_settings().cohere_api_key.get_secret_value()
        self._http = httpx.AsyncClient(timeout=30)

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=15),
        reraise=True,
    )
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankResult]:
        if not documents:
            return []
        response = await self._http.post(
            COHERE_RERANK_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
            },
        )
        response.raise_for_status()
        return [
            RerankResult(index=item["index"], score=item["relevance_score"])
            for item in response.json()["results"]
        ]

    async def aclose(self) -> None:
        await self._http.aclose()


class FakeReranker(Reranker):
    """Jaccard token overlap. Deterministic, offline."""

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankResult]:
        query_tokens = set(query.lower().split())
        scored = []
        for i, doc in enumerate(documents):
            doc_tokens = set(doc.lower().split())
            union = query_tokens | doc_tokens
            score = len(query_tokens & doc_tokens) / len(union) if union else 0.0
            scored.append(RerankResult(index=i, score=score))
        scored.sort(key=lambda r: (-r.score, r.index))
        return scored[:top_n]
