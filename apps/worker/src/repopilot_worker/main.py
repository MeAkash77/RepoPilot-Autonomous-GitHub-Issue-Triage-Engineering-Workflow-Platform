"""arq worker settings.

Run with: uv run arq repopilot_worker.main.WorkerSettings
Failed jobs retry with arq's backoff up to max_tries; the final failure
stays ledgered in webhook_deliveries with status='failed' (our dead-letter
record) and the error captured.
"""

from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

from arq.connections import RedisSettings

from repopilot_core.logging import configure_logging
from repopilot_core.settings import get_settings
from repopilot_core.telemetry import init_telemetry
from repopilot_worker.handlers import process_webhook

_settings = get_settings()
configure_logging(_settings.environment, _settings.log_level)
init_telemetry("worker")


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job proving the queue round-trips."""
    return "pong"


class WorkerSettings:
    functions: ClassVar[list[Callable[..., Coroutine[Any, Any, Any]]]] = [
        ping,
        process_webhook,
    ]
    redis_settings: ClassVar[RedisSettings] = RedisSettings.from_dsn(str(get_settings().redis_url))
    max_tries = 5
    retry_jobs = True
    job_timeout = 120
