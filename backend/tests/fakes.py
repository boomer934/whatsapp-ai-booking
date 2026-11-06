"""Implementazioni in memoria di store, sender, LLM e notifiche per i test."""

from datetime import UTC, datetime, time
from typing import Any
from uuid import UUID, uuid4

from backend.app.models.enums import (
    ConversationMode,
    ConversationState,
    MessagingProviderName,
)
from backend.app.models.schemas import (
    BusinessHours,
    Conversation,
    InboundMessage,
    Service,
    Tenant,
)
from backend.app.services.llm.base import LLMError
from backend.app.services.messaging.base import MessagingClient


def make_service(tenant_id: UUID, name: str, minutes: int, price_cents: int | None) -> Service:
    return Service(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name,
        duration_minutes=minutes,
        price_cents=price_cents,
    )


def weekly_hours() -> list[BusinessHours]:
    """Mar-Sab 09:00-13:00 e 14:30-19:00 (come il seed)."""
    return [
        BusinessHours(weekday=d, open_time=o, close_time=c)
        for d in range(1, 6)
        for o, c in ((time(9, 0), time(13, 0)), (time(14, 30), time(19, 0)))
    ]


def make_tenant(**overrides: object) -> Tenant:
    data: dict[str, object] = {
        "id": uuid4(),
        "name": "Salone Test",
        "timezone": "Europe/Rome",
        "ai_enabled": True,
        "messaging_provider": MessagingProviderName.META,
        "wa_phone_number_id": "PNID-1",
        "wa_phone_e164": "+14155238886",
        "operator_phone": "+390000000000",
    }
    data.update(overrides)
    return Tenant.model_validate(data)


def make_message(**overrides: object) -> InboundMessage:
    data: dict[str, object] = {
        "provider": MessagingProviderName.META,
        "provider_message_id": "wamid.1",
        "routing_key": "PNID-1",
        "customer_phone": "+393331112222",
        "customer_name": "Mario",
        "text": "Vorrei prenotare un taglio",
        "received_at": datetime.now(UTC),
    }
    data.update(overrides)
    return InboundMessage.model_validate(data)


class FakeStore:
    def __init__(self, tenants: list[Tenant]) -> None:
        self.tenants = tenants
        self.conversations: dict[tuple[UUID, str], Conversation] = {}
        self.inbound_ids: set[tuple[UUID, str]] = set()
        self.outbound: list[tuple[UUID, str, str | None]] = []
        # Storico (conversation_id, direzione, testo) per le viste del simulatore.
        self.log: list[tuple[UUID, str, str]] = []

    async def get_tenant_by_routing_key(
        self, provider: MessagingProviderName, routing_key: str
    ) -> Tenant | None:
        for tenant in self.tenants:
            key = {
                MessagingProviderName.META: tenant.wa_phone_number_id,
                MessagingProviderName.TWILIO: tenant.wa_phone_e164,
                MessagingProviderName.SIMULATOR: str(tenant.id),
            }[provider]
            if key == routing_key:
                return tenant
        return None

    async def get_or_create_conversation(
        self, tenant_id: UUID, customer_phone: str, customer_name: str | None
    ) -> Conversation:
        key = (tenant_id, customer_phone)
        if key not in self.conversations:
            self.conversations[key] = Conversation(
                id=uuid4(),
                tenant_id=tenant_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                state=ConversationState.IDLE,
                mode=ConversationMode.AI,
                failed_attempts=0,
            )
        return self.conversations[key]

    async def save_inbound_message(
        self, conversation: Conversation, message: InboundMessage
    ) -> bool:
        key = (conversation.tenant_id, message.provider_message_id)
        if key in self.inbound_ids:
            return False
        self.inbound_ids.add(key)
        self.log.append((conversation.id, "inbound", message.text or "[messaggio non testuale]"))
        return True

    async def save_outbound_message(
        self, conversation: Conversation, body: str, provider_message_id: str | None
    ) -> None:
        self.outbound.append((conversation.id, body, provider_message_id))
        self.log.append((conversation.id, "outbound", body))

    async def has_outbound_messages(self, conversation: Conversation) -> bool:
        return any(conversation_id == conversation.id for conversation_id, _, _ in self.outbound)


class FakeSender(MessagingClient):
    def __init__(self) -> None:
        self.sent: list[tuple[UUID, str, str]] = []

    async def send_text(self, tenant: Tenant, to_phone: str, body: str) -> str | None:
        self.sent.append((tenant.id, to_phone, body))
        return f"sent-{len(self.sent)}"


class FakeBookingStore(FakeStore):
    """FakeStore con catalogo, orari e prenotazioni (per il motore AI)."""

    def __init__(
        self,
        tenants: list[Tenant],
        services: list[Service] | None = None,
        hours: list[BusinessHours] | None = None,
    ) -> None:
        super().__init__(tenants)
        self.services = services or []
        self.hours = hours if hours is not None else weekly_hours()
        self.bookings: list[tuple[UUID, datetime, datetime]] = []
        self.google_events: dict[UUID, str] = {}
        self.updates = 0

    async def update_conversation(self, conversation: Conversation) -> None:
        self.updates += 1
        self.conversations[(conversation.tenant_id, conversation.customer_phone)] = conversation

    async def list_active_services(self, tenant_id: UUID) -> list[Service]:
        return [s for s in self.services if s.tenant_id == tenant_id and s.is_active]

    async def list_business_hours(self, tenant_id: UUID) -> list[BusinessHours]:
        return self.hours

    async def list_busy_intervals(
        self, tenant_id: UUID, start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        return [(s, e) for _, s, e in self.bookings if s < end and start < e]

    async def create_booking(
        self,
        conversation: Conversation,
        service: Service,
        starts_at: datetime,
        ends_at: datetime,
    ) -> UUID | None:
        if any(s < ends_at and starts_at < e for _, s, e in self.bookings):
            return None
        self.bookings.append((service.id, starts_at, ends_at))
        return uuid4()

    async def set_booking_google_event(
        self, tenant_id: UUID, booking_id: UUID, google_event_id: str
    ) -> None:
        self.google_events[booking_id] = google_event_id


class ScriptedLLM:
    """LLM finto: restituisce in ordine le risposte preparate (dict o eccezione)."""

    name = "scripted"

    def __init__(self, *responses: dict[str, Any] | LLMError) -> None:
        self.responses = list(responses)
        self.prompts: list[tuple[str, str]] = []

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        self.prompts.append((system_prompt, user_prompt))
        response = self.responses.pop(0)
        if isinstance(response, LLMError):
            raise response
        return response


class RecordingNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str]] = []

    async def notify_handover(
        self,
        tenant: Tenant,
        conversation: Conversation,
        last_message: str | None,
        reason: str,
    ) -> None:
        self.calls.append((conversation.id, reason))


# Variabili d'ambiente minime e valide per avviare l'app in production nei test
# (valori fittizi: nessun servizio reale viene contattato).
PRODUCTION_ENV: dict[str, str] = {
    "ENVIRONMENT": "production",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_test",
    "FRONTEND_URL": "https://dashboard.example.com",
    "PUBLIC_BASE_URL": "https://api.example.com",
    "GROQ_API_KEY": "gsk_test",
    "ENCRYPTION_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    "GOOGLE_CLIENT_ID": "client-id",
    "GOOGLE_CLIENT_SECRET": "client-secret",
    "GOOGLE_REDIRECT_URI": "https://api.example.com/oauth/google/callback",
}
