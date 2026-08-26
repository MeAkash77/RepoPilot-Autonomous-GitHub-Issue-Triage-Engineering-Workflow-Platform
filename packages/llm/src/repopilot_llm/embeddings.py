"""Embedding provider abstraction.

Production uses Gemini's embedding endpoint (free tier) truncated to
EMBEDDING_DIM via output_dimensionality (Matryoshka-trained, so truncation
is sound). Tests use the deterministic fake. Both normalize to unit length
so cosine distance behaves identically across providers.
"""

import hashlib
import math
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from repopilot_core.settings import get_settings

EMBEDDING_DIM = 1024
GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
)


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into unit-normalized EMBEDDING_DIM vectors."""


class GeminiEmbeddingProvider(EmbeddingProvider):
    BATCH_SIZE = 100  # API limit per batchEmbedContents call

    def __init__(self, model: str = "gemini-embedding-001") -> None:
        self._model = model
        self._api_key = get_settings().google_api_key.get_secret_value()
        self._http = httpx.AsyncClient(timeout=60)

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=15),
        reraise=True,
    )
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._http.post(
            GEMINI_EMBED_URL.format(model=self._model),
            params={"key": self._api_key},
            json={
                "requests": [
                    {
                        "model": f"models/{self._model}",
                        "content": {"parts": [{"text": text}]},
                        "outputDimensionality": EMBEDDING_DIM,
                    }
                    for text in texts
                ]
            },
        )
        response.raise_for_status()
        return [_normalize(item["values"]) for item in response.json()["embeddings"]]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            results.extend(await self._embed_batch(texts[start : start + self.BATCH_SIZE]))
        return results

    async def aclose(self) -> None:
        await self._http.aclose()


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embeddings for tests: token-hash bag-of-words. Texts
    sharing words get high cosine similarity, disjoint texts near zero."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * EMBEDDING_DIM
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
                vector[index] += 1.0
            vectors.append(_normalize(vector))
        return vectors
