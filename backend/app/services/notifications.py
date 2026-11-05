"""Notifiche all'operatore dell'attività (handover umano).

Nota: con la WhatsApp Cloud API un messaggio libero verso l'operatore viene
consegnato solo se l'operatore ha scritto al numero business nelle ultime 24 ore;
in produzione servirà un template approvato. La conversazione resta comunque
segnata come "manual" e visibile in dashboard.
"""

import logging
from collections.abc import Mapping
from typing import Protocol

from backend.app.models.enums import MessagingProviderName
from backend.app.models.schemas import Conversation, Tenant
from backend.app.services.messaging.base import MessagingClient

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    async def notify_handover(
        self,
        tenant: Tenant,
        conversation: Conversation,
        last_message: str | None,
        reason: str,
    ) -> None: ...


def build_handover_text(
    tenant: Tenant, conversation: Conversation, last_message: str | None, reason: str
) -> str:
    customer = " ".join(p for p in (conversation.customer_name, conversation.customer_phone) if p)
    lines = [
        f"🔔 {tenant.name}: una chat WhatsApp richiede il tuo intervento.",
        f"Cliente: {customer}",
        f"Motivo: {reason}",
    ]
    if last_message:
        lines.append(f'Ultimo messaggio: "{last_message[:200]}"')
    return "\n".join(lines)


class WhatsAppOperatorNotifier:
    def __init__(self, senders: Mapping[MessagingProviderName, MessagingClient]) -> None:
        self._senders = senders

    async def notify_handover(
        self,
        tenant: Tenant,
        conversation: Conversation,
        last_message: str | None,
        reason: str,
    ) -> None:
        if not tenant.operator_phone:
            logger.warning("Tenant %s senza operator_phone: handover non notificato", tenant.id)
            return
        text = build_handover_text(tenant, conversation, last_message, reason)
        try:
            await self._senders[tenant.messaging_provider].send_text(
                tenant, tenant.operator_phone, text
            )
        except Exception:
            logger.exception("Notifica handover fallita per il tenant %s", tenant.id)
