"""Interfaccia di persistenza usata dalla pipeline dei messaggi.

Separata dall'implementazione Supabase per poterla sostituire nei test.
"""

from typing import Protocol
from uuid import UUID

from backend.app.models.enums import MessagingProviderName
from backend.app.models.schemas import Conversation, InboundMessage, Tenant


class ConversationStore(Protocol):
    async def get_tenant_by_routing_key(
        self, provider: MessagingProviderName, routing_key: str
    ) -> Tenant | None:
        """Trova il tenant a cui è indirizzato il messaggio."""
        ...

    async def get_or_create_conversation(
        self, tenant_id: UUID, customer_phone: str, customer_name: str | None
    ) -> Conversation:
        """Restituisce la conversazione (tenant, numero cliente), creandola se serve."""
        ...

    async def save_inbound_message(
        self, conversation: Conversation, message: InboundMessage
    ) -> bool:
        """Salva il messaggio in arrivo. Restituisce False se è un duplicato."""
        ...

    async def save_outbound_message(
        self, conversation: Conversation, body: str, provider_message_id: str | None
    ) -> None:
        """Salva una risposta inviata al cliente."""
        ...
