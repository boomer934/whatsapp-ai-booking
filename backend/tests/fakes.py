"""Implementazioni in memoria di store e sender per i test."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.models.enums import (
    ConversationMode,
    ConversationState,
    MessagingProviderName,
)
from backend.app.models.schemas import Conversation, InboundMessage, Tenant
from backend.app.services.messaging.base import MessagingClient


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

    async def get_tenant_by_routing_key(
        self, provider: MessagingProviderName, routing_key: str
    ) -> Tenant | None:
        for tenant in self.tenants:
            key = (
                tenant.wa_phone_number_id
                if provider == MessagingProviderName.META
                else tenant.wa_phone_e164
            )
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
        return True

    async def save_outbound_message(
        self, conversation: Conversation, body: str, provider_message_id: str | None
    ) -> None:
        self.outbound.append((conversation.id, body, provider_message_id))


class FakeSender(MessagingClient):
    def __init__(self) -> None:
        self.sent: list[tuple[UUID, str, str]] = []

    async def send_text(self, tenant: Tenant, to_phone: str, body: str) -> str | None:
        self.sent.append((tenant.id, to_phone, body))
        return f"sent-{len(self.sent)}"
