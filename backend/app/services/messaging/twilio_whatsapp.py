"""Adapter per Twilio WhatsApp (Sandbox o numero approvato)."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.app.models.enums import MessagingProviderName
from backend.app.models.schemas import InboundMessage, Tenant
from backend.app.services.messaging.base import MessagingClient, MessagingError, to_e164

TWILIO_API_BASE_URL = "https://api.twilio.com/2010-04-01"


def parse_twilio_form(form: Mapping[str, str]) -> InboundMessage | None:
    """Converte i parametri del webhook Twilio in un messaggio normalizzato."""
    message_sid = form.get("MessageSid")
    sender = form.get("From")
    recipient = form.get("To")
    if not message_sid or not sender or not recipient:
        return None
    body = form.get("Body", "").strip()
    return InboundMessage(
        provider=MessagingProviderName.TWILIO,
        provider_message_id=message_sid,
        routing_key=to_e164(recipient),
        customer_phone=to_e164(sender),
        customer_name=form.get("ProfileName") or None,
        # Messaggi solo-media (audio, foto) arrivano con Body vuoto.
        text=body or None,
        received_at=datetime.now(UTC),
    )


class TwilioWhatsAppClient(MessagingClient):
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._http_client = http_client

    async def send_text(self, tenant: Tenant, to_phone: str, body: str) -> str | None:
        if not self._account_sid or not self._auth_token:
            raise MessagingError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN non configurati.")
        if not tenant.wa_phone_e164:
            raise MessagingError(f"Tenant {tenant.id} senza wa_phone_e164.")

        url = f"{TWILIO_API_BASE_URL}/Accounts/{self._account_sid}/Messages.json"
        data = {
            "From": f"whatsapp:{tenant.wa_phone_e164}",
            "To": f"whatsapp:{to_phone}",
            "Body": body,
        }
        auth = (self._account_sid, self._auth_token)

        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(url, data=data, auth=auth)
        finally:
            if self._http_client is None:
                await client.aclose()

        if response.is_error:
            raise MessagingError(f"Twilio API {response.status_code}: {response.text}")
        result: dict[str, Any] = response.json()
        return result.get("sid")
