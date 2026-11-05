"""Webhook di Twilio WhatsApp (Sandbox)."""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import Response

from backend.app.api.deps import get_inbound_processor
from backend.app.core.config import Settings, get_settings
from backend.app.core.security import verify_twilio_signature
from backend.app.services.conversation.inbound import InboundProcessor
from backend.app.services.messaging.twilio_whatsapp import parse_twilio_form

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["webhooks"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
ProcessorDep = Annotated[InboundProcessor, Depends(get_inbound_processor)]

# TwiML vuoto: la risposta viene inviata in modo asincrono via REST API.
EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def public_request_url(request: Request, settings: Settings) -> str:
    """Ricostruisce l'URL pubblico firmato da Twilio (anche dietro il proxy di Render)."""
    if settings.public_base_url:
        url = settings.public_base_url.rstrip("/") + request.url.path
        return f"{url}?{request.url.query}" if request.url.query else url
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto:
        return str(request.url.replace(scheme=forwarded_proto))
    return str(request.url)


@router.post("")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    processor: ProcessorDep,
) -> Response:
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}

    auth_token = settings.twilio_auth_token.get_secret_value()
    if auth_token:
        signature = request.headers.get("X-Twilio-Signature")
        url = public_request_url(request, settings)
        if not verify_twilio_signature(url, params, signature, auth_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Firma non valida")
    elif settings.is_production:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "TWILIO_AUTH_TOKEN non configurato")
    else:
        logger.warning("TWILIO_AUTH_TOKEN vuoto: verifica firma saltata (solo development)")

    message = parse_twilio_form(params)
    if message is not None:
        background_tasks.add_task(processor.process_safely, message)
    return Response(content=EMPTY_TWIML, media_type="application/xml")
