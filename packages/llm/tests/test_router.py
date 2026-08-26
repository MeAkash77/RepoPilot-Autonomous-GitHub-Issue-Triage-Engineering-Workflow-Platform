import pytest
from pydantic import BaseModel, Field

from repopilot_llm.router import FakeChatProvider, LLMRouter, RouteConfig


class _Out(BaseModel):
    answer: str
    score: float


class _Capped(BaseModel):
    summary: str = Field(max_length=20)
    note: str | None = Field(default=None, max_length=10)


def _router(provider: FakeChatProvider) -> LLMRouter:
    return LLMRouter(
        routes={
            "classify": RouteConfig(
                provider="fake",
                model="fake-model",
                temperature=0.0,
                input_cost_per_mtok=1.0,
                output_cost_per_mtok=2.0,
            )
        },
        providers={"fake": provider},
    )


async def test_complete_returns_cost_from_token_counts() -> None:
    router = _router(FakeChatProvider(default="hello"))
    response = await router.complete("classify", [{"role": "user", "content": "hi"}])
    assert response.text == "hello"
    # 100 input tokens * $1/M + 50 output * $2/M
    assert response.cost_usd == pytest.approx((100 * 1.0 + 50 * 2.0) / 1_000_000)


async def test_complete_structured_parses_and_appends_schema() -> None:
    provider = FakeChatProvider(default='{"answer": "ok", "score": 0.9}')
    router = _router(provider)
    parsed, _ = await router.complete_structured(
        "classify", [{"role": "system", "content": "sys"}], schema=_Out
    )
    assert parsed.answer == "ok"
    assert "JSON Schema" in provider.calls[0]["messages"][0]["content"]


async def test_complete_structured_strips_code_fences() -> None:
    provider = FakeChatProvider(default='```json\n{"answer": "ok", "score": 1.0}\n```')
    parsed, _ = await _router(provider).complete_structured(
        "classify", [{"role": "user", "content": "x"}], schema=_Out
    )
    assert parsed.score == 1.0


async def test_complete_structured_clamps_overlong_strings() -> None:
    # Weak models overrun max_length; the parser truncates instead of crashing.
    long = "the model rambled far past the cap with too many words here"
    provider = FakeChatProvider(default=f'{{"summary": "{long}", "note": null}}')
    parsed, _ = await _router(provider).complete_structured(
        "classify", [{"role": "user", "content": "x"}], schema=_Capped
    )
    assert len(parsed.summary) <= 20
    assert parsed.summary.endswith("…")


async def test_complete_structured_clamps_optional_field() -> None:
    provider = FakeChatProvider(default='{"summary": "fine", "note": "way too long to fit"}')
    parsed, _ = await _router(provider).complete_structured(
        "classify", [{"role": "user", "content": "x"}], schema=_Capped
    )
    assert parsed.note is not None and len(parsed.note) <= 10


async def test_unknown_route_raises() -> None:
    router = _router(FakeChatProvider())
    with pytest.raises(KeyError):
        await router.complete("nonexistent", [])
