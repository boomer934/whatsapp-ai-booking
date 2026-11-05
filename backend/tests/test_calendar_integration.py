"""Conversazioni con Google Calendar collegato (Google simulato, nessuna rete)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.app.core.crypto import TokenCipher
from backend.app.models.enums import ConversationMode, ConversationState
from backend.app.models.schemas import GoogleCredentials
from backend.tests.google_fake import (
    TEST_KEY,
    FakeAdminStore,
    FakeGoogle,
    build_service,
)
from backend.tests.test_state_machine import TOMORROW, Harness, booking

ROME = ZoneInfo("Europe/Rome")
FRIDAY_15 = datetime(2026, 11, 6, 15, 0, tzinfo=ROME)


def harness_with_calendar(*llm: dict[str, object], connected: bool = True) -> tuple[Harness, FakeGoogle]:
    google, admin = FakeGoogle(), FakeAdminStore()
    calendar = build_service(google, admin)
    h = Harness(*llm, calendar=calendar)
    calendar._booking_store = h.store  # collega l'evento alla prenotazione nel fake store
    if connected:
        admin.credentials[h.tenant.id] = GoogleCredentials(
            tenant_id=h.tenant.id,
            refresh_token_encrypted=TokenCipher(TEST_KEY).encrypt("refresh-1"),
        )
    return h, google


def test_google_event_blocks_requested_slot() -> None:
    h, google = harness_with_calendar(booking(service_number=2, date=TOMORROW, time="15:00"))
    google.busy = [(FRIDAY_15, FRIDAY_15 + timedelta(hours=1))]  # impegno del titolare

    reply = h.send("taglio uomo domani alle 15")
    assert reply is not None and reply.startswith("Alle 15:00 non c'è posto.")
    assert "1. ven 6/11 ore 14:30" in reply


def test_confirmed_booking_creates_google_event() -> None:
    h, google = harness_with_calendar(
        booking(service_number=2, date=TOMORROW, time="15:00"), {"intent": "confirm"}
    )
    h.send("taglio uomo domani alle 15")
    reply = h.send("sì")

    assert reply is not None and "confermata" in reply
    [event] = google.events
    assert event["summary"] == "Taglio uomo - Mario"
    assert event["start"]["dateTime"] == "2026-11-06T15:00:00+01:00"
    assert h.store.google_events == {next(iter(h.store.google_events)): "evt-1"}


def test_event_added_after_proposal_is_detected_at_confirmation() -> None:
    h, google = harness_with_calendar(
        booking(service_number=2, date=TOMORROW, time="15:00"), {"intent": "confirm"}
    )
    h.send("taglio uomo domani alle 15")
    google.busy = [(FRIDAY_15, FRIDAY_15 + timedelta(minutes=30))]  # aggiunto nel frattempo

    reply = h.send("sì")
    assert reply is not None and reply.startswith("Quell'orario non è più disponibile.")
    assert h.store.bookings == [] and google.events == []


def test_google_down_hands_over_instead_of_guessing() -> None:
    h, google = harness_with_calendar(booking(service_number=2, date=TOMORROW, time="15:00"))
    google.fail_calendar = True

    reply = h.send("taglio uomo domani alle 15")
    assert reply is not None and "staff" in reply
    assert h.conversation.mode == ConversationMode.MANUAL
    assert "calendario" in h.notifier.calls[0][1]


def test_google_down_at_confirmation_hands_over() -> None:
    h, google = harness_with_calendar(
        booking(service_number=2, date=TOMORROW, time="15:00"), {"intent": "confirm"}
    )
    h.send("taglio uomo domani alle 15")
    google.fail_calendar = True

    reply = h.send("sì")
    assert reply is not None and "staff" in reply
    assert h.store.bookings == []


def test_without_connected_calendar_booking_works_as_before() -> None:
    h, google = harness_with_calendar(
        booking(service_number=2, date=TOMORROW, time="15:00"), {"intent": "confirm"}, connected=False
    )
    h.send("taglio uomo domani alle 15")
    reply = h.send("sì")
    assert reply is not None and "confermata" in reply
    assert h.conversation.state == ConversationState.COMPLETED
    assert google.calls == []
