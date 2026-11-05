"""Test end-to-end del motore conversazionale con LLM finto e orologio fisso."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.app.models.enums import ConversationMode, ConversationState, MessagingProviderName
from backend.app.models.schemas import Conversation
from backend.app.services.calendar.availability import AvailabilityService, CombinedBusyProvider
from backend.app.services.conversation.inbound import InboundProcessor
from backend.app.services.conversation.interpreter import MessageInterpreter
from backend.app.services.conversation.state_machine import NON_TEXT_REPLY, AiReplyEngine
from backend.app.services.llm.base import LLMError
from backend.tests.fakes import (
    FakeBookingStore,
    FakeSender,
    RecordingNotifier,
    ScriptedLLM,
    make_message,
    make_service,
    make_tenant,
)

ROME = ZoneInfo("Europe/Rome")
# Giovedì 5 novembre 2026, ore 10:00 a Roma.
NOW = datetime(2026, 11, 5, 10, 0, tzinfo=ROME)
TOMORROW = "2026-11-06"


class Harness:
    def __init__(
        self,
        *llm_responses: dict[str, Any] | LLMError,
        single_service: bool = False,
        calendar: Any = None,
    ) -> None:
        self.tenant = make_tenant()
        all_services = [
            make_service(self.tenant.id, "Taglio donna", 45, 3500),
            make_service(self.tenant.id, "Taglio uomo", 30, 2000),
            make_service(self.tenant.id, "Piega", 30, 2500),
            make_service(self.tenant.id, "Colore", 90, 6000),
        ]
        self.services = all_services[:1] if single_service else all_services
        self.store = FakeBookingStore([self.tenant], self.services)
        self.llm = ScriptedLLM(*llm_responses)
        self.notifier = RecordingNotifier()
        # Con un calendario esterno (GoogleCalendarService) si usa la stessa
        # composizione di produzione: DB + free/busy, ed eventi alla conferma.
        provider = CombinedBusyProvider(self.store, calendar) if calendar else self.store
        self.engine = AiReplyEngine(
            store=self.store,
            interpreter=MessageInterpreter(self.llm),
            availability=AvailabilityService(provider),
            notifier=self.notifier,
            booking_sync=calendar,
            clock=lambda: NOW.astimezone(UTC),
        )
        self._counter = 0

    @property
    def conversation(self) -> Conversation:
        return asyncio.run(
            self.store.get_or_create_conversation(self.tenant.id, "+393331112222", "Mario")
        )

    def send(self, text: str | None) -> str | None:
        self._counter += 1
        message = make_message(text=text, provider_message_id=f"m{self._counter}")
        return asyncio.run(self.engine.reply(self.tenant, self.conversation, message))


def booking(**fields: Any) -> dict[str, Any]:
    return {"intent": "booking_request", **fields}


# --------------------------------------------------------------- happy paths


def test_full_booking_in_two_messages() -> None:
    h = Harness(
        booking(service_number=1, date=TOMORROW, time="15:00"),
        {"intent": "confirm"},
    )

    reply = h.send("Vorrei un taglio donna domani verso le 15")
    assert reply == "Perfetto: Taglio donna, venerdì 6 novembre alle 15:00. Confermi la prenotazione?"
    assert h.conversation.state == ConversationState.CONFIRMING

    reply = h.send("sì")
    assert reply is not None and reply.startswith("Prenotazione confermata ✅")
    assert h.conversation.state == ConversationState.COMPLETED
    assert h.conversation.context == {}
    [(service_id, start, end)] = h.store.bookings
    assert service_id == h.services[0].id
    assert start == datetime(2026, 11, 6, 15, 0, tzinfo=ROME)
    assert (end - start).seconds == 45 * 60


def test_booking_with_service_question_and_slot_choice() -> None:
    h = Harness(
        booking(),
        booking(service_number=4),
        booking(slot_number=2),
        {"intent": "confirm"},
    )

    reply = h.send("Vorrei prenotare")
    assert reply is not None and "Quale servizio desideri?" in reply and "4. Colore (90 min, 60 €)" in reply
    assert h.conversation.state == ConversationState.SELECTING_SERVICE

    reply = h.send("il colore")
    assert reply is not None and "1. gio 5/11 ore 11:00\n2. gio 5/11 ore 11:30\n3. gio 5/11 ore 14:30" in reply
    assert h.conversation.state == ConversationState.SELECTING_SLOT

    reply = h.send("il secondo")
    assert reply == "Perfetto: Colore, giovedì 5 novembre alle 11:30. Confermi la prenotazione?"

    reply = h.send("ok")
    assert reply is not None and "confermata" in reply
    assert h.store.bookings[0][1] == datetime(2026, 11, 5, 11, 30, tzinfo=ROME)


def test_preferences_given_before_service_are_kept() -> None:
    h = Harness(booking(date=TOMORROW, time="15:00"), booking(service_number=2))
    h.send("domani alle 15 si può?")
    assert h.conversation.state == ConversationState.SELECTING_SERVICE
    reply = h.send("taglio uomo")
    assert reply == "Perfetto: Taglio uomo, venerdì 6 novembre alle 15:00. Confermi la prenotazione?"


def test_single_service_is_selected_automatically() -> None:
    h = Harness(booking(date=TOMORROW, time="09:00"), single_service=True)
    reply = h.send("domani alle 9")
    assert reply is not None and reply.startswith("Perfetto: Taglio donna")


def test_requested_time_busy_proposes_alternatives() -> None:
    h = Harness(booking(service_number=2, date=TOMORROW, time="15:00"))
    friday_15 = datetime(2026, 11, 6, 15, 0, tzinfo=ROME)
    h.store.bookings.append((uuid4(), friday_15, friday_15.replace(hour=16)))

    reply = h.send("taglio uomo domani alle 15")
    assert reply is not None and reply.startswith("Alle 15:00 non c'è posto.")
    assert "1. ven 6/11 ore 14:30" in reply
    assert h.conversation.state == ConversationState.SELECTING_SLOT


def test_slot_taken_between_proposal_and_confirmation() -> None:
    h = Harness(booking(service_number=2, date=TOMORROW, time="15:00"), {"intent": "confirm"})
    h.send("taglio uomo domani alle 15")
    friday_15 = datetime(2026, 11, 6, 15, 0, tzinfo=ROME)
    h.store.bookings.append((uuid4(), friday_15, friday_15.replace(hour=16)))  # altro cliente

    reply = h.send("sì")
    assert reply is not None and reply.startswith("Quell'orario non è più disponibile.")
    assert h.conversation.state == ConversationState.SELECTING_SLOT
    assert len(h.store.bookings) == 1


def test_concurrent_booking_rejected_by_database() -> None:
    """Ricontrollo superato ma il DB rifiuta (gara con un'altra prenotazione)."""
    h = Harness(booking(service_number=2, date=TOMORROW, time="15:00"), {"intent": "confirm"})
    h.send("taglio uomo domani alle 15")

    async def rejected(*args: object) -> None:
        # Un altro cliente ha appena occupato lo stesso orario.
        friday_15 = datetime(2026, 11, 6, 15, 0, tzinfo=ROME)
        h.store.bookings.append((uuid4(), friday_15, friday_15.replace(minute=30)))
        return None

    h.store.create_booking = rejected  # type: ignore[method-assign]
    reply = h.send("sì")
    assert reply is not None and reply.startswith("Quell'orario è appena stato prenotato.")
    assert h.conversation.state == ConversationState.SELECTING_SLOT


# ------------------------------------------------------- domande e rifiuti


def test_question_mid_flow_answers_and_reminds_step() -> None:
    h = Harness(
        booking(service_number=1, date=TOMORROW, time="15:00"),
        {"intent": "question", "answer": "Il taglio donna costa 35 €."},
    )
    h.send("taglio donna domani alle 15")
    reply = h.send("quanto costa?")
    assert reply == (
        "Il taglio donna costa 35 €.\n\n"
        "Confermi Taglio donna, venerdì 6 novembre alle 15:00?"
    )
    assert h.conversation.state == ConversationState.CONFIRMING


def test_decline_while_confirming_asks_new_preference() -> None:
    h = Harness(booking(service_number=1, date=TOMORROW, time="15:00"), {"intent": "decline"})
    h.send("taglio donna domani alle 15")
    reply = h.send("no, non mi va bene")
    assert reply == "Nessun problema! Che giorno e orario preferisci?"
    assert h.conversation.state == ConversationState.SELECTING_SLOT
    assert h.conversation.context == {"service_id": str(h.services[0].id)}


def test_decline_with_new_time_reschedules_directly() -> None:
    h = Harness(
        booking(service_number=1, date=TOMORROW, time="15:00"),
        {"intent": "decline", "time": "17:00"},
    )
    h.send("taglio donna domani alle 15")
    reply = h.send("no, meglio alle 17")
    assert reply == "Perfetto: Taglio donna, venerdì 6 novembre alle 17:00. Confermi la prenotazione?"


def test_availability_question_is_treated_as_booking() -> None:
    h = Harness({"intent": "question", "service_number": 3, "date": "2026-11-07", "part_of_day": "morning"})
    reply = h.send("si può fare sabato mattina una piega?")
    assert reply is not None and "1. sab 7/11 ore 09:00" in reply
    assert h.conversation.state == ConversationState.SELECTING_SLOT


# ---------------------------------------------------------------- handover


def test_two_consecutive_failures_trigger_handover() -> None:
    h = Harness({"intent": "unclear"}, {"intent": "unclear"})

    reply = h.send("asdfgh")
    assert reply == "Scusa, non ho capito. Vuoi prenotare un appuntamento?"
    assert h.conversation.failed_attempts == 1
    assert h.conversation.mode == ConversationMode.AI

    reply = h.send("qwerty")
    assert reply is not None and "staff" in reply
    assert h.conversation.mode == ConversationMode.MANUAL
    assert len(h.notifier.calls) == 1


def test_understood_message_resets_failure_counter() -> None:
    h = Harness({"intent": "unclear"}, booking(), {"intent": "unclear"})
    h.send("asdfgh")
    h.send("vorrei prenotare")
    assert h.conversation.failed_attempts == 0
    h.send("???")
    assert h.conversation.mode == ConversationMode.AI


def test_llm_outage_counts_as_failure() -> None:
    h = Harness(LLMError("timeout"), LLMError("timeout"))
    h.send("ciao")
    h.send("ciao?")
    assert h.conversation.mode == ConversationMode.MANUAL


def test_human_request_hands_over_immediately() -> None:
    h = Harness({"intent": "human"})
    reply = h.send("voglio parlare con qualcuno")
    assert reply is not None and "staff" in reply
    assert h.conversation.mode == ConversationMode.MANUAL
    assert h.notifier.calls


def test_invalid_slot_number_counts_as_failure() -> None:
    h = Harness(booking(service_number=2), booking(slot_number=7))
    h.send("taglio uomo")
    reply = h.send("il settimo")
    assert reply is not None and reply.startswith("Scusa, non ho capito.")
    assert h.conversation.failed_attempts == 1


# -------------------------------------------------------------- casi limite


def test_non_text_message_skips_llm() -> None:
    h = Harness()
    assert h.send(None) == NON_TEXT_REPLY
    assert h.llm.prompts == []


def test_completed_conversation_restarts() -> None:
    h = Harness(
        booking(service_number=1, date=TOMORROW, time="15:00"),
        {"intent": "confirm"},
        {"intent": "greeting", "answer": "Grazie a te!"},
    )
    h.send("taglio donna domani alle 15")
    h.send("sì")
    assert h.send("grazie") == "Grazie a te!"
    assert h.conversation.state == ConversationState.IDLE


def test_no_services_hands_over() -> None:
    h = Harness()
    h.store.services = []
    reply = h.send("ciao")
    assert reply is not None and "staff" in reply
    assert h.llm.prompts == []


def test_unavailable_preference_falls_back_to_first_free_slots() -> None:
    h = Harness(booking(service_number=2, date="2026-11-08"))  # domenica: chiuso
    reply = h.send("taglio uomo domenica")
    # Domenica chiuso: la ricerca prosegue dai giorni successivi.
    assert reply is not None and "1. mar 10/11 ore 09:00" in reply


# ------------------------------------------------- integrazione con pipeline


def test_pipeline_stops_replying_after_handover() -> None:
    h = Harness({"intent": "human"})
    sender = FakeSender()
    processor = InboundProcessor(
        store=h.store,
        engine=h.engine,
        senders={MessagingProviderName.META: sender, MessagingProviderName.TWILIO: sender},
    )
    asyncio.run(processor.process(make_message(text="un operatore per favore", provider_message_id="a")))
    asyncio.run(processor.process(make_message(text="ci sei?", provider_message_id="b")))

    assert len(sender.sent) == 1  # solo il messaggio di handover
    assert h.llm.prompts and len(h.llm.prompts) == 1


def test_time_without_date_prefers_closest_on_first_open_day() -> None:
    h = Harness(booking(service_number=2, time="16:00"))
    reply = h.send("taglio uomo alle 16")
    assert reply is not None and "1. gio 5/11 ore 15:30\n2. gio 5/11 ore 16:00\n3. gio 5/11 ore 16:30" in reply
