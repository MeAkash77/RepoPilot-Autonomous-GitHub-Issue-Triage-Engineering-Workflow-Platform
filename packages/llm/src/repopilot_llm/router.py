"""LLMRouter: per-node model routing with cost accounting, fallback, and circuit breaker.

Each agent node declares a route name; the router maps it to a provider +
model from YAML config (packages/agent/config/models.yaml). Cheap fast
models handle classification; an `escalation` route exists for one retry
of a low-confidence node with a stronger model. Every call returns exact
token counts and dollar cost so runs can enforce a per-run cost ceiling.

Reliability additions:
- Optional fallback_provider / fallback_model per route in YAML.
- Redis-backed CircuitBreaker: opens after N failures, routes to fallback
  during the open window, recovers via half-open probe.
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import httpx
import structlog
import yaml
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from repopilot_core.settings import get_settings

logger = structlog.get_logger()
SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Circuit breaker config
_CB_FAILURE_THRESHOLD = 5  # open after N consecutive failures
_CB_COOLDOWN_SECONDS = 60  # stay open for this long
_CB_KEY_PREFIX = "rp:cb:"  # Redis key prefix


@dataclass
class RouteConfig:
    provider: str
    model: str
    temperature: float
    input_cost_per_mtok: float
    output_cost_per_mtok: float
    fallback_provider: str | None = field(default=None)
    fallback_model: str | None = field(default=None)


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    used_fallback: bool = False


def _field_max_length(spec: dict[str, Any]) -> int | None:
    if "maxLength" in spec:
        return int(spec["maxLength"])
    for sub in spec.get("anyOf", []):
        if isinstance(sub, dict) and "maxLength" in sub:
            return int(sub["maxLength"])
    return None


def _clamp_string_lengths(data: Any, json_schema: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        return
    for name, spec in json_schema.get("properties", {}).items():
        value = data.get(name)
        if not isinstance(value, str) or not isinstance(spec, dict):
            continue
        cap = _field_max_length(spec)
        if cap is None or len(value) <= cap:
            continue
        head = value[: cap - 1].rstrip()
        if " " in head:
            head = head[: head.rfind(" ")].rstrip()
        data[name] = f"{head}…"


class ChatProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        """Return (text, input_tokens, output_tokens)."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return isinstance(exc, httpx.TransportError)


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=20),
    reraise=True,
)


class GroqProvider(ChatProvider):
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self._api_key = get_settings().groq_api_key.get_secret_value()
        self._http = httpx.AsyncClient(timeout=60)

    @_retry
    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        response = await self._http.post(
            self.BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage", {})
        return (
            data["choices"][0]["message"]["content"],
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )


class GeminiProvider(ChatProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self) -> None:
        self._api_key = get_settings().google_api_key.get_secret_value()
        self._http = httpx.AsyncClient(timeout=90)

    @_retry
    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
            if m["role"] != "system"
        ]
        generation_config: dict[str, Any] = {"temperature": temperature}
        if json_schema is not None:
            generation_config["responseMimeType"] = "application/json"
        payload: dict[str, Any] = {"contents": contents, "generationConfig": generation_config}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        response = await self._http.post(
            self.BASE_URL.format(model=model),
            params={"key": self._api_key},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usageMetadata", {})
        return (
            data["candidates"][0]["content"]["parts"][0]["text"],
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )


class FakeChatProvider(ChatProvider):
    """Scripted responses keyed by route hint in the first system message."""

    def __init__(self, responses: dict[str, str] | None = None, default: str = "{}") -> None:
        self.responses = responses or {}
        self.default = default
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        self.calls.append({"model": model, "messages": messages})
        text_out = self.default
        for key, value in self.responses.items():
            if any(key in m["content"] for m in messages):
                text_out = value
                break
        return text_out, 100, 50


class CircuitBreaker:
    """Redis-backed per-provider circuit breaker.

    States:
      closed  — normal operation, tracking failure count
      open    — provider failed N times; short-circuit to fallback
      half-open — cooldown expired, next call is a probe
    """

    def __init__(self, provider_name: str) -> None:
        self._name = provider_name
        self._key_fail = f"{_CB_KEY_PREFIX}{provider_name}:failures"
        self._key_opened = f"{_CB_KEY_PREFIX}{provider_name}:opened_at"
        self._redis: Any | None = None

    async def _get_redis(self) -> Any | None:
        if self._redis is not None:
            return self._redis
        settings = get_settings()
        if settings.environment == "local":
            return None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(str(settings.redis_url), decode_responses=True)  # type: ignore[no-untyped-call]
        except Exception:
            pass
        return self._redis

    async def is_open(self) -> bool:
        r = await self._get_redis()
        if r is None:
            return False
        opened_at = await r.get(self._key_opened)
        if opened_at is None:
            return False
        if time.time() - float(opened_at) > _CB_COOLDOWN_SECONDS:
            # Cooldown expired — allow half-open probe
            await r.delete(self._key_opened)
            return False
        return True

    async def record_failure(self) -> None:
        r = await self._get_redis()
        if r is None:
            return
        count = await r.incr(self._key_fail)
        await r.expire(self._key_fail, _CB_COOLDOWN_SECONDS * 2)
        if int(count) >= _CB_FAILURE_THRESHOLD:
            existing = await r.get(self._key_opened)
            if existing is None:
                await r.set(self._key_opened, str(time.time()), ex=_CB_COOLDOWN_SECONDS * 2)
                logger.warning("llm.circuit_open", provider=self._name, failures=count)

    async def record_success(self) -> None:
        r = await self._get_redis()
        if r is None:
            return
        await r.delete(self._key_fail)
        await r.delete(self._key_opened)


class LLMRouter:
    def __init__(
        self,
        routes: dict[str, RouteConfig],
        providers: dict[str, ChatProvider],
    ) -> None:
        self._routes = routes
        self._providers = providers
        self._breakers: dict[str, CircuitBreaker] = {}

    def _breaker(self, provider_name: str) -> CircuitBreaker:
        if provider_name not in self._breakers:
            self._breakers[provider_name] = CircuitBreaker(provider_name)
        return self._breakers[provider_name]

    @classmethod
    def from_yaml(cls, path: Path, providers: dict[str, ChatProvider]) -> "LLMRouter":
        raw = yaml.safe_load(path.read_text())
        routes = {
            name: RouteConfig(
                provider=cfg["provider"],
                model=cfg["model"],
                temperature=cfg.get("temperature", 0.0),
                input_cost_per_mtok=cfg.get("input_cost_per_mtok", 0.0),
                output_cost_per_mtok=cfg.get("output_cost_per_mtok", 0.0),
                fallback_provider=cfg.get("fallback_provider"),
                fallback_model=cfg.get("fallback_model"),
            )
            for name, cfg in raw["routes"].items()
        }
        return cls(routes, providers)

    def route(self, name: str) -> RouteConfig:
        if name not in self._routes:
            raise KeyError(f"no route named {name!r}")
        return self._routes[name]

    async def _call_provider(
        self,
        provider_name: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        provider = self._providers[provider_name]
        return await provider.complete(model, messages, temperature, json_schema)

    async def _complete_with_fallback(
        self,
        config: RouteConfig,
        messages: list[dict[str, str]],
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, int, int, str, str, bool]:
        """Returns (text, in_tok, out_tok, provider, model, used_fallback)."""
        breaker = self._breaker(config.provider)
        use_fallback = await breaker.is_open()

        if not use_fallback:
            try:
                text, in_tok, out_tok = await self._call_provider(
                    config.provider, config.model, messages, temperature, json_schema
                )
                await breaker.record_success()
                return text, in_tok, out_tok, config.provider, config.model, False
            except Exception as exc:
                await breaker.record_failure()
                logger.warning(
                    "llm.primary_failed",
                    provider=config.provider,
                    model=config.model,
                    error=repr(exc),
                )
                if config.fallback_provider is None or config.fallback_model is None:
                    raise
                use_fallback = True

        if use_fallback and config.fallback_provider and config.fallback_model:
            logger.info(
                "llm.fallback",
                primary=config.provider,
                fallback=config.fallback_provider,
                model=config.fallback_model,
            )
            text, in_tok, out_tok = await self._call_provider(
                config.fallback_provider, config.fallback_model, messages, temperature, json_schema
            )
            return text, in_tok, out_tok, config.fallback_provider, config.fallback_model, True

        raise RuntimeError(f"no fallback configured for provider {config.provider!r}")

    async def complete(
        self,
        route_name: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> LLMResponse:
        config = self.route(route_name)
        temp = config.temperature if temperature is None else temperature
        text, in_tok, out_tok, _prov, model, fallback = await self._complete_with_fallback(
            config, messages, temp, None
        )
        return LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=(in_tok * config.input_cost_per_mtok + out_tok * config.output_cost_per_mtok)
            / 1_000_000,
            model=model,
            used_fallback=fallback,
        )

    async def complete_structured(
        self,
        route_name: str,
        messages: list[dict[str, str]],
        schema: type[SchemaT],
        temperature: float | None = None,
    ) -> tuple[SchemaT, LLMResponse]:
        config = self.route(route_name)
        json_schema = schema.model_json_schema()
        schema_hint = (
            "\n\nRespond with a single JSON object matching this JSON Schema exactly:\n"
            + json.dumps(json_schema)
        )
        augmented = [dict(m) for m in messages]
        if augmented and augmented[0]["role"] == "system":
            augmented[0]["content"] += schema_hint
        else:
            augmented.insert(0, {"role": "system", "content": schema_hint.strip()})

        temp = config.temperature if temperature is None else temperature
        text, in_tok, out_tok, _prov, model, fallback = await self._complete_with_fallback(
            config, augmented, temp, json_schema
        )

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            raw = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = schema.model_validate_json(cleaned)
        else:
            _clamp_string_lengths(raw, json_schema)
            parsed = schema.model_validate(raw)

        response = LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=(in_tok * config.input_cost_per_mtok + out_tok * config.output_cost_per_mtok)
            / 1_000_000,
            model=model,
            used_fallback=fallback,
        )
        return parsed, response
