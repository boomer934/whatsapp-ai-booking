"""Modelli Pydantic di dominio condivisi tra API, servizi e repository."""

from datetime import datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import (
    ConversationMode,
    ConversationState,
    MessagingProviderName,
)


class InboundMessage(BaseModel):
    """Messaggio WhatsApp in arrivo, normalizzato e indipendente dal provider."""

    model_config = ConfigDict(frozen=True)

    provider: MessagingProviderName
    provider_message_id: str
    # Chiave per individuare il tenant: phone_number_id (Meta) o numero E.164 (Twilio).
    routing_key: str
    customer_phone: str = Field(description="Numero del cliente in formato E.164")
    customer_name: str | None = None
    # None se il messaggio non è testuale (audio, immagine, ...).
    text: str | None = None
    received_at: datetime


class Tenant(BaseModel):
    id: UUID
    name: str
    timezone: str
    ai_enabled: bool
    messaging_provider: MessagingProviderName
    wa_phone_number_id: str | None = None
    wa_phone_e164: str | None = None
    operator_phone: str | None = None


class Service(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    duration_minutes: int
    price_cents: int | None = None
    is_active: bool = True


class BusinessHours(BaseModel):
    """Fascia di apertura. weekday: 0 = lunedì ... 6 = domenica."""

    weekday: int = Field(ge=0, le=6)
    open_time: time
    close_time: time


class Conversation(BaseModel):
    id: UUID
    tenant_id: UUID
    customer_phone: str
    customer_name: str | None = None
    state: ConversationState
    mode: ConversationMode
    failed_attempts: int
    context: dict[str, Any] = Field(default_factory=dict)
