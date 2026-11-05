"""Motore conversazionale AI: interpretazione -> transizione di stato -> risposta.

Flusso tipico (2-4 scambi):
  idle --(richiesta)--> selecting_service --(servizio)--> selecting_slot
       --(scelta orario)--> confirming --(sì)--> completed

L'LLM interpreta i messaggi; tutte le risposte su disponibilità e prenotazioni
sono generate qui da template, così l'AI non può inventare orari.
Dopo MAX_FAILED_ATTEMPTS messaggi non compresi la chat passa all'operatore.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.app.models.enums import MAX_FAILED_ATTEMPTS, ConversationMode, ConversationState
from backend.app.models.schemas import Conversation, InboundMessage, Service, Tenant
from backend.app.repositories.base import ConversationStore
from backend.app.services.calendar.availability import (
    AvailabilityService,
    CalendarUnavailableError,
)
from backend.app.services.conversation.context import BookingContext
from backend.app.services.conversation.formatting import (
    format_service_list,
    format_slot,
    format_slot_list,
)
from backend.app.services.conversation.interpreter import (
    Intent,
    Interpretation,
    InterpretationError,
    MessageInterpreter,
)
from backend.app.services.notifications import Notifier

logger = logging.getLogger(__name__)

NON_TEXT_REPLY = "Per ora riesco a leggere solo messaggi di testo. Puoi scrivermi?"
CALENDAR_DOWN_REASON = "il calendario collegato non è raggiungibile: verificare il collegamento Google"


class BookingSync(Protocol):
    """Notificato dopo ogni prenotazione confermata (es. evento su Google Calendar).
    Le implementazioni non devono sollevare eccezioni."""

    async def on_booking_confirmed(
        self,
        tenant: Tenant,
        conversation: Conversation,
        service: Service,
        booking_id: UUID,
        start: datetime,
        end: datetime,
    ) -> None: ...


class NoBookingSync:
    async def on_booking_confirmed(
        self,
        tenant: Tenant,
        conversation: Conversation,
        service: Service,
        booking_id: UUID,
        start: datetime,
        end: datetime,
    ) -> None:
        return None


@dataclass
class _Turn:
    """Tutto ciò che serve per gestire un singolo messaggio."""

    tenant: Tenant
    conversation: Conversation
    context: BookingContext
    services: list[Service]
    message: InboundMessage
    now: datetime  # nel fuso del tenant

    @property
    def state(self) -> ConversationState:
        return self.conversation.state

    @property
    def service(self) -> Service | None:
        return next((s for s in self.services if s.id == self.context.service_id), None)


class AiReplyEngine:
    def __init__(
        self,
        store: ConversationStore,
        interpreter: MessageInterpreter,
        availability: AvailabilityService,
        notifier: Notifier,
        booking_sync: BookingSync | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._interpreter = interpreter
        self._availability = availability
        self._notifier = notifier
        self._booking_sync: BookingSync = booking_sync or NoBookingSync()
        self._clock = clock

    # ------------------------------------------------------------------ entry

    async def reply(
        self, tenant: Tenant, conversation: Conversation, message: InboundMessage
    ) -> str | None:
        if message.text is None:
            return NON_TEXT_REPLY

        if conversation.state == ConversationState.COMPLETED:
            conversation.state = ConversationState.IDLE
            conversation.context = {}

        turn = _Turn(
            tenant=tenant,
            conversation=conversation,
            context=BookingContext.from_conversation(conversation),
            services=await self._store.list_active_services(tenant.id),
            message=message,
            now=self._clock().astimezone(ZoneInfo(tenant.timezone)),
        )
        if not turn.services:
            return await self._handover(turn, "nessun servizio prenotabile configurato")

        try:
            interpretation = await self._interpreter.interpret(
                tenant=tenant,
                services=turn.services,
                hours=await self._store.list_business_hours(tenant.id),
                state=turn.state,
                context=turn.context,
                text=message.text,
                now=turn.now,
            )
        except InterpretationError as exc:
            logger.warning("Interpretazione fallita (%s): %s", conversation.id, exc)
            return await self._fail(turn)

        return await self._dispatch(turn, interpretation)

    async def _dispatch(self, turn: _Turn, interp: Interpretation) -> str:
        match interp.intent:
            case Intent.HUMAN:
                return await self._handover(turn, "il cliente chiede un operatore o ha una richiesta complessa")
            case Intent.UNCLEAR:
                return await self._fail(turn)
            case Intent.QUESTION if interp.has_time_preference:
                # "Avete posto sabato?" è una richiesta di disponibilità.
                return await self._booking(turn, interp)
            case Intent.QUESTION | Intent.GREETING:
                return await self._answer(turn, interp)
            case Intent.CONFIRM:
                return await self._confirm(turn, interp)
            case Intent.DECLINE:
                return await self._decline(turn, interp)
            case Intent.BOOKING_REQUEST:
                return await self._booking(turn, interp)
            case _:
                return await self._fail(turn)

    # --------------------------------------------------------------- intents

    async def _answer(self, turn: _Turn, interp: Interpretation) -> str:
        if interp.answer is None:
            if interp.intent == Intent.QUESTION:
                return await self._fail(turn)
            answer = f"Ciao! Sono l'assistente di {turn.tenant.name}. Vuoi prenotare un appuntamento?"
        else:
            answer = interp.answer
        reminder = self._step_prompt(turn)
        await self._save(turn, turn.state)
        return f"{answer}\n\n{reminder}" if reminder else answer

    async def _confirm(self, turn: _Turn, interp: Interpretation) -> str:
        ctx = turn.context
        if turn.state == ConversationState.CONFIRMING and ctx.selected_slot:
            return await self._book(turn)
        if turn.state == ConversationState.SELECTING_SLOT and len(ctx.proposed_slots) == 1:
            ctx.selected_slot = ctx.proposed_slots[0]
            return await self._book(turn)
        if interp.has_booking_details:
            return await self._booking(turn, interp)
        return await self._fail(turn)

    async def _decline(self, turn: _Turn, interp: Interpretation) -> str:
        if interp.has_booking_details:
            return await self._booking(turn, interp)
        if turn.state in (ConversationState.CONFIRMING, ConversationState.SELECTING_SLOT):
            service_id = turn.context.service_id
            turn.context = BookingContext(service_id=service_id)
            await self._save(turn, ConversationState.SELECTING_SLOT)
            return "Nessun problema! Che giorno e orario preferisci?"
        turn.context = BookingContext()
        await self._save(turn, ConversationState.IDLE)
        return "Va bene! Se ti serve altro, scrivimi pure."

    async def _booking(self, turn: _Turn, interp: Interpretation) -> str:
        ctx = turn.context
        if interp.service is not None:
            ctx.service_id = interp.service.id
        if turn.service is None and len(turn.services) == 1:
            ctx.service_id = turn.services[0].id

        # Scelta di uno degli orari proposti ("il secondo").
        if interp.slot_number is not None and ctx.proposed_slots:
            if not 1 <= interp.slot_number <= len(ctx.proposed_slots):
                return await self._fail(turn)
            ctx.selected_slot = ctx.proposed_slots[interp.slot_number - 1]
            service = turn.service
            if service is not None:
                await self._save(turn, ConversationState.CONFIRMING)
                return self._confirm_prompt(service, ctx.selected_slot)

        # Nuove preferenze di giorno/ora: si sommano a quelle già espresse.
        if interp.day is not None:
            ctx.day = interp.day
        if interp.at is not None:
            ctx.at, ctx.part_of_day = interp.at, None
        if interp.part_of_day is not None:
            ctx.part_of_day, ctx.at = interp.part_of_day, None

        service = turn.service
        if service is None:
            await self._save(turn, ConversationState.SELECTING_SERVICE)
            return "Certo! Quale servizio desideri?\n" + format_service_list(turn.services)
        return await self._propose(turn, service)

    # ----------------------------------------------------------- transitions

    async def _propose(self, turn: _Turn, service: Service, prefix: str = "") -> str:
        ctx = turn.context
        try:
            slots = await self._availability.find_slots(
                turn.tenant, service, turn.now, ctx.day, ctx.at, ctx.part_of_day
            )
            has_preferences = any(v is not None for v in (ctx.day, ctx.at, ctx.part_of_day))
            if not slots and has_preferences:
                prefix += "In quel momento non ho disponibilità. "
                ctx.day, ctx.at, ctx.part_of_day = None, None, None
                slots = await self._availability.find_slots(turn.tenant, service, turn.now)
        except CalendarUnavailableError:
            return await self._handover(turn, CALENDAR_DOWN_REASON)
        if not slots:
            return await self._handover(turn, f"nessuna disponibilità trovata per {service.name}")

        requested = (
            datetime.combine(ctx.day, ctx.at, tzinfo=turn.now.tzinfo)
            if ctx.day is not None and ctx.at is not None
            else None
        )
        if requested is not None and slots == [requested]:
            ctx.selected_slot, ctx.proposed_slots = requested, []
            await self._save(turn, ConversationState.CONFIRMING)
            return prefix + self._confirm_prompt(service, requested)

        if requested is not None:
            prefix += f"Alle {requested:%H:%M} non c'è posto. "
        ctx.proposed_slots, ctx.selected_slot = slots, None
        await self._save(turn, ConversationState.SELECTING_SLOT)
        return (
            f"{prefix}Per {service.name} ho questi orari liberi:\n"
            f"{format_slot_list(slots)}\nQuale preferisci? Rispondi con il numero."
        )

    async def _book(self, turn: _Turn) -> str:
        ctx = turn.context
        service = turn.service
        if service is None or ctx.selected_slot is None:
            return await self._fail(turn)

        start = ctx.selected_slot.astimezone(turn.now.tzinfo)
        # Ricontrollo: il tempo passa e il titolare può aver aggiunto impegni.
        try:
            still_free = await self._availability.is_available(
                turn.tenant, service, start, turn.now
            )
        except CalendarUnavailableError:
            return await self._handover(turn, CALENDAR_DOWN_REASON)
        if not still_free:
            ctx.selected_slot = None
            return await self._propose(turn, service, "Quell'orario non è più disponibile. ")

        end = start + timedelta(minutes=service.duration_minutes)
        booking_id = await self._store.create_booking(turn.conversation, service, start, end)
        if booking_id is None:
            ctx.selected_slot = None
            return await self._propose(turn, service, "Quell'orario è appena stato prenotato. ")

        turn.context = BookingContext()
        await self._save(turn, ConversationState.COMPLETED)
        await self._booking_sync.on_booking_confirmed(
            turn.tenant, turn.conversation, service, booking_id, start, end
        )
        return (
            f"Prenotazione confermata ✅\n{service.name}, {format_slot(start)}.\n"
            f"A presto da {turn.tenant.name}!"
        )

    async def _fail(self, turn: _Turn) -> str:
        turn.conversation.failed_attempts += 1
        if turn.conversation.failed_attempts >= MAX_FAILED_ATTEMPTS:
            return await self._handover(
                turn, f"l'assistente non ha capito il cliente per {MAX_FAILED_ATTEMPTS} volte"
            )
        await self._save(turn, turn.state, reset_failures=False)
        return "Scusa, non ho capito. " + self._retry_prompt(turn)

    async def _handover(self, turn: _Turn, reason: str) -> str:
        conversation = turn.conversation
        conversation.mode = ConversationMode.MANUAL
        await self._save(turn, turn.state)
        await self._notifier.notify_handover(turn.tenant, conversation, turn.message.text, reason)
        return (
            f"Ti metto in contatto con lo staff di {turn.tenant.name}: "
            "ti risponderà appena possibile."
        )

    # --------------------------------------------------------------- helpers

    async def _save(
        self, turn: _Turn, state: ConversationState, reset_failures: bool = True
    ) -> None:
        conversation = turn.conversation
        conversation.state = state
        conversation.context = turn.context.to_json()
        if reset_failures:
            conversation.failed_attempts = 0
        await self._store.update_conversation(conversation)

    @staticmethod
    def _confirm_prompt(service: Service, slot: datetime) -> str:
        return f"Perfetto: {service.name}, {format_slot(slot)}. Confermi la prenotazione?"

    def _step_prompt(self, turn: _Turn) -> str:
        """Ricorda al cliente il passo in corso (dopo una risposta informativa)."""
        ctx = turn.context
        match turn.state:
            case ConversationState.SELECTING_SERVICE:
                return "Quale servizio desideri?\n" + format_service_list(turn.services)
            case ConversationState.SELECTING_SLOT if ctx.proposed_slots:
                return "Quale orario preferisci?\n" + format_slot_list(ctx.proposed_slots)
            case ConversationState.SELECTING_SLOT:
                return "Che giorno e orario preferisci?"
            case ConversationState.CONFIRMING if ctx.selected_slot and turn.service:
                return f"Confermi {turn.service.name}, {format_slot(ctx.selected_slot)}?"
            case _:
                return ""

    def _retry_prompt(self, turn: _Turn) -> str:
        match turn.state:
            case ConversationState.SELECTING_SERVICE:
                return "Rispondi con il numero del servizio:\n" + format_service_list(turn.services)
            case ConversationState.SELECTING_SLOT:
                return "Rispondi con il numero dell'orario oppure indicami giorno e ora."
            case ConversationState.CONFIRMING:
                return 'Rispondi "sì" per confermare o "no" per scegliere un altro orario.'
            case _:
                return "Vuoi prenotare un appuntamento?"
