import math

from repopilot_llm.embeddings import EMBEDDING_DIM, FakeEmbeddingProvider
from repopilot_llm.reranker import FakeReranker


async def test_fake_embeddings_unit_norm_and_deterministic() -> None:
    provider = FakeEmbeddingProvider()
    [a1] = await provider.embed(["auth token expires early"])
    [a2] = await provider.embed(["auth token expires early"])
    assert a1 == a2
    assert len(a1) == EMBEDDING_DIM
    assert abs(math.sqrt(sum(v * v for v in a1)) - 1.0) < 1e-9


async def test_fake_embeddings_similarity_orders_sensibly() -> None:
    provider = FakeEmbeddingProvider()
    query, similar, unrelated = await provider.embed(
        [
            "login button crashes the app",
            "app crashes when login button pressed",
            "documentation typo in readme",
        ]
    )

    def cosine(x: list[float], y: list[float]) -> float:
        return sum(a * b for a, b in zip(x, y, strict=True))

    assert cosine(query, similar) > cosine(query, unrelated)


async def test_fake_reranker_orders_by_overlap() -> None:
    reranker = FakeReranker()
    results = await reranker.rerank(
        "database connection timeout",
        ["unrelated text entirely", "database connection timeout in pool", "timeout"],
        top_n=3,
    )
    assert results[0].index == 1
    assert len(results) == 3


async def test_fake_reranker_empty_documents() -> None:
    assert await FakeReranker().rerank("q", [], top_n=5) == []
