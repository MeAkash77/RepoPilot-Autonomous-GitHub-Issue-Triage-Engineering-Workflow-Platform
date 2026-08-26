"""GitHub webhook receiver.

Contract: verify HMAC signature, record the delivery in the idempotency
ledger, check per-installation daily budget, enqueue processing, return 202
immediately. All real work happens in the worker — this handler must stay
fast and side-effect-minimal.
"""

import json
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from repopilot_api.deps import DbSession, Queue
from repopilot_core.db import WebhookDelivery
from repopilot_core.db.models import WebhookDeliveryStatus
from repopilot_core.settings import get_settings
from repopilot_github.webhooks import payload_hash, verify_signature

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Events we act on; everything else is acknowledged and skipped.
HANDLED_EVENTS = {
    "installation",
    "installation_repositories",
    "issues",
}

# Maximum webhook body (enforced by SecurityMiddleware via Content-Length;
# this is a belt-and-suspenders explicit cap for chunked bodies).
_MAX_BODY_BYTES = 2 * 1024 * 1024


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    db: DbSession,
    queue: Queue,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(...),
    x_hub_signature_256: str | None = Header(None),
) -> Response:
    # Explicit body-size guard for chunked transfers (no Content-Length).
    body = await request.body()
    if len(body) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")

    secret = get_settings().github_webhook_secret.get_secret_value()
    if not verify_signature(secret, body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="invalid signature")

    if x_github_event not in HANDLED_EVENTS:
        return Response(status_code=status.HTTP_202_ACCEPTED)

    delivery = WebhookDelivery(
        github_delivery_id=x_github_delivery,
        event_type=x_github_event,
        payload_hash=payload_hash(body),
        payload=json.loads(body),
        status=WebhookDeliveryStatus.RECEIVED,
    )
    db.add(delivery)
    try:
        await db.commit()
    except IntegrityError:
        # Duplicate delivery (GitHub redelivery or retry) — already ledgered.
        await db.rollback()
        existing = await db.scalar(
            select(WebhookDelivery).where(WebhookDelivery.github_delivery_id == x_github_delivery)
        )
        logger.info(
            "webhook.duplicate",
            delivery_id=x_github_delivery,
            status=existing.status if existing else None,
        )
        return Response(status_code=status.HTTP_202_ACCEPTED)

    # Per-installation daily budget — only enforced for issue events that
    # trigger the LLM pipeline. Installation/repository events are cheap.
    if x_github_event == "issues":
        payload = delivery.payload or {}
        installation_id = (payload.get("installation") or {}).get("id")
        if installation_id is not None:
            settings = get_settings()
            date_key = datetime.now(UTC).strftime("%Y%m%d")
            budget_key = f"budget:{installation_id}:{date_key}"
            # Atomic increment — TTL of 26h covers day-boundary edge cases.
            current = await queue.incr(budget_key)
            if current == 1:
                await queue.expire(budget_key, 26 * 3600)
            if current > settings.max_runs_per_install_per_day:
                delivery.status = WebhookDeliveryStatus.THROTTLED
                await db.commit()
                logger.warning(
                    "webhook.throttled",
                    delivery_id=x_github_delivery,
                    installation_id=installation_id,
                    daily_count=current,
                    cap=settings.max_runs_per_install_per_day,
                )
                return Response(status_code=status.HTTP_202_ACCEPTED)

    await queue.enqueue_job("process_webhook", delivery.id)
    delivery.status = WebhookDeliveryStatus.ENQUEUED
    await db.commit()
    logger.info("webhook.enqueued", delivery_id=x_github_delivery, event_type=x_github_event)
    return Response(status_code=status.HTTP_202_ACCEPTED)
