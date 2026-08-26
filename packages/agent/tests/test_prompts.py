from repopilot_agent.graph import MODELS_CONFIG_PATH, make_router
from repopilot_agent.prompts.registry import load_prompt
from repopilot_llm.router import FakeChatProvider


def test_all_prompts_load_with_versions() -> None:
    for name in ("classify", "condense_query", "duplicate_check", "info_gap"):
        prompt = load_prompt(name)
        assert prompt.version
        assert prompt.body


def test_classify_prompt_renders() -> None:
    text = load_prompt("classify").render(
        repo_full_name="a/b", context="ctx", few_shot="", title="T", body="B"
    )
    assert "<issue_data>" in text
    assert "a/b" in text


def test_models_config_covers_all_routes() -> None:
    fake = FakeChatProvider()
    router = make_router({"groq": fake, "gemini": fake})
    for route in ("condense_query", "classify", "duplicate_check", "info_gap", "escalation"):
        assert router.route(route).model


def test_models_config_path_exists() -> None:
    assert MODELS_CONFIG_PATH.exists()
