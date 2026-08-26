from repopilot_core.settings import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "local"
    assert settings.max_cost_per_run_usd == 0.02


def test_secrets_not_leaked_in_repr() -> None:
    settings = Settings(_env_file=None, github_webhook_secret="supersecret")  # type: ignore[arg-type]
    assert "supersecret" not in repr(settings)
    assert "supersecret" not in str(settings)
