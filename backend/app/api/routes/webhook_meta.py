"""Webhook della WhatsApp Business Cloud API (Meta)."""

import hmac
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from backend.app.api.deps import get_inbound_processor
from backend.app.core.config import Settings, get_settings
from backend.app.core.security import verify_meta_signature
from backend.app.services.conversation.inbound import InboundProcessor
from backend.app.services.messaging.meta_whatsapp import parse_meta_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
ProcessorDep = Annotated[InboundProcessor, Depends(get_inbound_processor)]


@router.get("", response_class=PlainTextResponse)
async def verify_subscription(
    settings: SettingsDep,
    hub_mode: Annotated[str, Query(alias="hub.mode")],
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")],
    hub_challenge: Annotated[str, Query(alias="hub.challenge")],
) -> str:
    """Handshake di verifica richiesto da Meta alla configurazione del webhook."""
    expected = settings.meta_verify_token.get_secret_value()
    if not expected or hub_mode != "subscribe" or not hmac.compare_digest(
        hub_verify_token, expected
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verifica webhook fallita")
    return hub_challenge


@router.post("")
async def receive_messages(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    processor: ProcessorDep,
) -> dict[str, str]:
    """Riceve i messaggi e risponde 200 subito; l'elaborazione avviene in background."""
    body = await request.body()

    app_secret = settings.meta_app_secret.get_secret_value()
    if app_secret:
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_meta_signature(body, signature, app_secret):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Firma non valida")
    elif settings.is_production:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "META_APP_SECRET non configurato")
    else:
        logger.warning("META_APP_SECRET vuoto: verifica firma saltata (solo development)")

    try:
        payload: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "JSON non valido") from exc

    for message in parse_meta_payload(payload):
        background_tasks.add_task(processor.process_safely, message)
    return {"status": "ok"}
