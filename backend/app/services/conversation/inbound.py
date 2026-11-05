"""Pipeline dei messaggi in arrivo: tenant -> conversazione -> dedup -> risposta."""

import logging
from collections.abc import Mapping

from backend.app.models.enums import ConversationMode, MessagingProviderName
from backend.app.models.schemas import InboundMessage
from backend.app.repositories.base import ConversationStore
from backend.app.services.conversation.engine import ReplyEngine
from backend.app.services.messaging.base import MessagingClient

logger = logging.getLogger(__name__)


class InboundProcessor:
    def __init__(
        self,
        store: ConversationStore,
        engine: ReplyEngine,
        senders: Mapping[MessagingProviderName, MessagingClient],
    ) -> None:
        self._store = store
        self._engine = engine
        self._senders = senders

    async def process(self, message: InboundMessage) -> None:
        tenant = await self._store.get_tenant_by_routing_key(
            message.provider, message.routing_key
        )
        if tenant is None:
            logger.warning(
                "Nessun tenant per %s routing_key=%s", message.provider, message.routing_key
            )
            return

        conversation = await self._store.get_or_create_conversation(
            tenant.id, message.customer_phone, message.customer_name
        )
        if not await self._store.save_inbound_message(conversation, message):
            logger.info("Messaggio duplicato ignorato: %s", message.provider_message_id)
            return

        # Assistente disattivato o chat in gestione all'operatore: si salva e basta.
        if not tenant.ai_enabled or conversation.mode == ConversationMode.MANUAL:
            return

        reply = await self._engine.reply(tenant, conversation, message)
        if not reply:
            return

        sender = self._senders[message.provider]
        provider_message_id = await sender.send_text(tenant, message.customer_phone, reply)
        await self._store.save_outbound_message(conversation, reply, provider_message_id)

    async def process_safely(self, message: InboundMessage) -> None:
        """Wrapper per i background task: un errore non deve mai propagarsi."""
        try:
            await self.process(message)
        except Exception:
            logger.exception(
                "Errore nell'elaborazione del messaggio %s", message.provider_message_id
            )
