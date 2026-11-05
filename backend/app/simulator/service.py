"""Simulatore WhatsApp: fa girare la pipeline reale (AI, DB, calendario) senza provider.

Ogni messaggio viene elaborato in modo sincrono con un InboundProcessor dedicato
i cui "sender" catturano i messaggi in uscita invece di inviarli: né il cliente
simulato né l'operatore ricevono messaggi reali.
"""

import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from backend.app.models.enums import ConversationMode, MessagingProviderName
from backend.app.models.schemas import InboundMessage, Tenant
from backend.app.repositories.base import ConversationStore
from backend.app.services.calendar.availability import AvailabilityService
from backend.app.services.conversation.inbound import InboundProcessor
from backend.app.services.conversation.interpreter import MessageInterpreter
from backend.app.services.conversation.state_machine import AiReplyEngine, BookingSync
from backend.app.services.messaging.base import MessagingClient, to_e164
from backend.app.services.notifications import WhatsAppOperatorNotifier
from backend.app.simulator.store import BookingSummary, ChatMessage, SimulatorStore, TenantSummary


class CapturingSender(MessagingClient):
    """Sender che registra i messaggi in uscita invece di inviarli."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, tenant: Tenant, to_phone: str, body: str) -> str | None:
        self.sent.append((to_phone, body))
        return f"sim-out-{uuid4()}"


class ConversationView(BaseModel):
    state: str
    mode: str
    failed_attempts: int
    context: dict[str, Any]


class SimulatorSnapshot(BaseModel):
    conversation: ConversationView | None
    messages: list[ChatMessage]
    bookings: list[BookingSummary]


class SimulatorTurn(BaseModel):
    replies: list[str]
    operator_notifications: list[str]
    note: str | None = None
    error: str | None = None
    elapsed_ms: int
    snapshot: SimulatorSnapshot


class SimulatorService:
    def __init__(
        self,
        store: ConversationStore,
        sim_store: SimulatorStore,
        interpreter: MessageInterpreter,
        availability: AvailabilityService,
        booking_sync: BookingSync | None = None,
    ) -> None:
        self._store = store
        self._sim_store = sim_store
        self._interpreter = interpreter
        self._availability = availability
        self._booking_sync = booking_sync

    async def tenants(self) -> list[TenantSummary]:
        return await self._sim_store.list_tenants()

    async def send(
        self, tenant_id: UUID, phone: str, name: str | None, text: str
    ) -> SimulatorTurn:
        customer_phone = to_e164(phone)
        capture = CapturingSender()
        senders: dict[MessagingProviderName, MessagingClient] = {
            provider: capture for provider in MessagingProviderName
        }
        engine = AiReplyEngine(
            store=self._store,
            interpreter=self._interpreter,
            availability=self._availability,
            notifier=WhatsAppOperatorNotifier(senders),
            booking_sync=self._booking_sync,
        )
        processor = InboundProcessor(store=self._store, engine=engine, senders=senders)
        message = InboundMessage(
            provider=MessagingProviderName.SIMULATOR,
            provider_message_id=f"sim-{uuid4()}",
            routing_key=str(tenant_id),
            customer_phone=customer_phone,
            customer_name=(name or "").strip() or None,
            text=text.strip() or None,
            received_at=datetime.now(UTC),
        )

        started = time.perf_counter()
        error: str | None = None
        try:
            await processor.process(message)
        except Exception as exc:  # mostrato nella pagina per il debug
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        replies = [body for to, body in capture.sent if to == customer_phone]
        notifications = [body for to, body in capture.sent if to != customer_phone]
        snapshot = await self.snapshot(tenant_id, customer_phone)
        return SimulatorTurn(
            replies=replies,
            operator_notifications=notifications,
            note=self._silence_reason(replies, error, snapshot),
            error=error,
            elapsed_ms=elapsed_ms,
            snapshot=snapshot,
        )

    async def snapshot(self, tenant_id: UUID, phone: str) -> SimulatorSnapshot:
        customer_phone = to_e164(phone)
        conversation = await self._sim_store.find_conversation(tenant_id, customer_phone)
        messages = (
            await self._sim_store.list_messages(tenant_id, conversation.id) if conversation else []
        )
        return SimulatorSnapshot(
            conversation=(
                ConversationView(
                    state=conversation.state.value,
                    mode=conversation.mode.value,
                    failed_attempts=conversation.failed_attempts,
                    context=conversation.context,
                )
                if conversation
                else None
            ),
            messages=messages,
            bookings=await self._sim_store.list_bookings(tenant_id, customer_phone),
        )

    async def reset(self, tenant_id: UUID, phone: str, include_bookings: bool) -> None:
        await self._sim_store.reset(tenant_id, to_e164(phone), include_bookings)

    async def resume_ai(self, tenant_id: UUID, phone: str) -> SimulatorSnapshot:
        await self._sim_store.resume_ai(tenant_id, to_e164(phone))
        return await self.snapshot(tenant_id, phone)

    @staticmethod
    def _silence_reason(
        replies: list[str], error: str | None, snapshot: SimulatorSnapshot
    ) -> str | None:
        if replies or error:
            return None
        conversation = snapshot.conversation
        if conversation is None:
            return "Nessuna risposta: attività non trovata."
        if conversation.mode == ConversationMode.MANUAL.value:
            return "Nessuna risposta: la chat è in gestione all'operatore."
        return "Nessuna risposta: l'assistente AI è disattivato per questa attività."
