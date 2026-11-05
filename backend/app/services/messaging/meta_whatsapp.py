"""Adapter per la WhatsApp Business Cloud API di Meta."""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.app.models.enums import MessagingProviderName
from backend.app.models.schemas import InboundMessage, Tenant
from backend.app.services.messaging.base import MessagingClient, MessagingError, to_e164

logger = logging.getLogger(__name__)

GRAPH_API_BASE_URL = "https://graph.facebook.com"


def _extract_text(message: dict[str, Any]) -> str | None:
    """Estrae il testo dai tipi di messaggio supportati (testo e risposte a bottoni)."""
    msg_type = message.get("type")
    if msg_type == "text":
        return message.get("text", {}).get("body")
    if msg_type == "button":
        return message.get("button", {}).get("text")
    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("title")
    return None


def parse_meta_payload(payload: dict[str, Any]) -> list[InboundMessage]:
    """Converte il payload webhook di Meta in messaggi normalizzati.

    Gli aggiornamenti di stato (sent/delivered/read) vengono ignorati.
    """
    messages: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            if not phone_number_id:
                continue
            names = {
                contact.get("wa_id"): contact.get("profile", {}).get("name")
                for contact in value.get("contacts", [])
            }
            for message in value.get("messages", []):
                sender = message.get("from")
                message_id = message.get("id")
                if not sender or not message_id:
                    continue
                timestamp = message.get("timestamp")
                received_at = (
                    datetime.fromtimestamp(int(timestamp), tz=UTC)
                    if timestamp
                    else datetime.now(UTC)
                )
                messages.append(
                    InboundMessage(
                        provider=MessagingProviderName.META,
                        provider_message_id=message_id,
                        routing_key=phone_number_id,
                        customer_phone=to_e164(sender),
                        customer_name=names.get(sender),
                        text=_extract_text(message),
                        received_at=received_at,
                    )
                )
    return messages


class MetaWhatsAppClient(MessagingClient):
    def __init__(
        self,
        access_token: str,
        api_version: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._api_version = api_version
        self._http_client = http_client

    async def send_text(self, tenant: Tenant, to_phone: str, body: str) -> str | None:
        if not self._access_token:
            raise MessagingError("META_ACCESS_TOKEN non configurato.")
        if not tenant.wa_phone_number_id:
            raise MessagingError(f"Tenant {tenant.id} senza wa_phone_number_id.")

        url = f"{GRAPH_API_BASE_URL}/{self._api_version}/{tenant.wa_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone.lstrip("+"),
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}

        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(url, json=payload, headers=headers)
        finally:
            if self._http_client is None:
                await client.aclose()

        if response.is_error:
            raise MessagingError(f"Meta API {response.status_code}: {response.text}")
        data: dict[str, Any] = response.json()
        sent = data.get("messages") or [{}]
        return sent[0].get("id")
