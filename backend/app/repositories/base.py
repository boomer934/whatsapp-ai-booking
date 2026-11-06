"""Interfaccia di persistenza usata dalla pipeline dei messaggi.

Separata dall'implementazione Supabase per poterla sostituire nei test.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.app.models.enums import MessagingProviderName
from backend.app.models.schemas import (
    BusinessHours,
    Conversation,
    InboundMessage,
    Service,
    Tenant,
)


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

    async def has_outbound_messages(self, conversation: Conversation) -> bool:
        """True se al cliente è già stata inviata almeno una risposta."""
        ...

    async def update_conversation(self, conversation: Conversation) -> None:
        """Persiste state, mode, failed_attempts, context e customer_name."""
        ...

    async def list_active_services(self, tenant_id: UUID) -> list[Service]:
        """Servizi prenotabili, in ordine stabile (la numerazione nel prompt dipende da questo)."""
        ...

    async def list_business_hours(self, tenant_id: UUID) -> list[BusinessHours]: ...

    async def list_busy_intervals(
        self, tenant_id: UUID, start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        """Prenotazioni confermate che intersecano [start, end)."""
        ...

    async def create_booking(
        self,
        conversation: Conversation,
        service: Service,
        starts_at: datetime,
        ends_at: datetime,
    ) -> UUID | None:
        """Crea la prenotazione. None se lo slot è già occupato (vincolo anti-overlap)."""
        ...

    async def set_booking_google_event(
        self, tenant_id: UUID, booking_id: UUID, google_event_id: str
    ) -> None:
        """Associa alla prenotazione l'evento creato su Google Calendar."""
        ...
