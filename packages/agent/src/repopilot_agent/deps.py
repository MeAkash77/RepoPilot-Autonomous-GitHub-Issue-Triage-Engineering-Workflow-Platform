"""Default NodeDeps factory for production entrypoints (worker, CLI).

Falls back to deterministic fakes when API keys are absent so local dev
without keys still exercises the full graph shape.
"""

import sys

from repopilot_agent.graph import make_router
from repopilot_agent.nodes import NodeDeps
from repopilot_core.db import get_session_factory
from repopilot_core.settings import get_settings
from repopilot_github.client import GitHubAppClient
from repopilot_llm.embeddings import FakeEmbeddingProvider, GeminiEmbeddingProvider
from repopilot_llm.reranker import CohereReranker, FakeReranker
from repopilot_llm.router import ChatProvider, FakeChatProvider, GeminiProvider, GroqProvider


def build_default_deps(installation_id: int | None = None) -> NodeDeps:
    settings = get_settings()

    providers: dict[str, ChatProvider] = {}
    if settings.groq_api_key.get_secret_value():
        providers["groq"] = GroqProvider()
    if settings.google_api_key.get_secret_value():
        providers["gemini"] = GeminiProvider()
    missing = {"groq", "gemini"} - providers.keys()
    if missing:
        print(f"! API keys missing for {sorted(missing)} — using FakeChatProvider", file=sys.stderr)
        fake = FakeChatProvider(
            default='{"type": "bug", "severity": 3, "confidence": 0.5, "reasoning_summary": "fake provider"}'
        )
        for name in missing:
            providers[name] = fake

    embedder = (
        GeminiEmbeddingProvider()
        if settings.google_api_key.get_secret_value()
        else FakeEmbeddingProvider()
    )
    reranker = CohereReranker() if settings.cohere_api_key.get_secret_value() else FakeReranker()
    github = GitHubAppClient() if settings.github_app_id else None

    return NodeDeps(
        session_factory=get_session_factory(),
        router=make_router(providers),
        embedder=embedder,
        reranker=reranker,
        github=github,
        installation_id=installation_id,
    )
