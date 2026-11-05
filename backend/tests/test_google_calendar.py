"""Test di cifratura, client Google e GoogleCalendarService (flusso OAuth incluso)."""

import asyncio
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet

from backend.app.core.crypto import CryptoConfigError, InvalidEncryptedValue, TokenCipher
from backend.app.models.schemas import Conversation
from backend.app.models.enums import ConversationMode, ConversationState
from backend.app.services.calendar.availability import CalendarUnavailableError
from backend.app.services.calendar.google_calendar import (
    GoogleNotConfiguredError,
    OAuthFlowError,
)
from backend.app.services.calendar.google_client import CALENDAR_EVENTS_SCOPE, REQUIRED_SCOPES
from backend.tests.fakes import make_service, make_tenant
from backend.tests.google_fake import (
    TEST_KEY,
    FakeAdminStore,
    FakeBookingEvents,
    FakeGoogle,
    build_service,
)

ROME = ZoneInfo("Europe/Rome")
TENANT = make_tenant()
USER = uuid4()


def connected_setup() -> tuple[FakeGoogle, FakeAdminStore, FakeBookingEvents]:
    """Tenant con calendario già collegato tramite il flusso OAuth reale."""
    google, admin, events = FakeGoogle(), FakeAdminStore({(TENANT.id, USER)}), FakeBookingEvents()
    service = build_service(google, admin, events)
    state = parse_qs(urlparse(service.authorization_url(TENANT.id, USER)).query)["state"][0]
    asyncio.run(service.complete_authorization("auth-code", state))
    return google, admin, events


# ------------------------------------------------------------------ crypto


def test_cipher_roundtrip_and_tampering() -> None:
    cipher = TokenCipher(TEST_KEY)
    token = cipher.encrypt("segreto")
    assert token != "segreto" and cipher.decrypt(token) == "segreto"
    with pytest.raises(InvalidEncryptedValue):
        cipher.decrypt(token[:-4] + "AAAA")
    with pytest.raises(InvalidEncryptedValue):
        TokenCipher(Fernet.generate_key().decode()).decrypt(token)


def test_cipher_state_expires() -> None:
    cipher = TokenCipher(TEST_KEY)
    state = cipher._fernet.encrypt_at_time(b'{"t": "x"}', current_time=0).decode()
    with pytest.raises(InvalidEncryptedValue):
        cipher.decrypt_json(state, ttl_seconds=600)


def test_cipher_requires_valid_key() -> None:
    with pytest.raises(CryptoConfigError):
        TokenCipher("")
    with pytest.raises(CryptoConfigError):
        TokenCipher("non-una-chiave")


# ----------------------------------------------------------- flusso OAuth


def test_authorization_url_contains_offline_access_and_minimal_scopes() -> None:
    service = build_service(FakeGoogle(), FakeAdminStore())
    query = parse_qs(urlparse(service.authorization_url(TENANT.id, USER)).query)
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert set(query["scope"][0].split()) >= REQUIRED_SCOPES
    assert "https://www.googleapis.com/auth/calendar" not in query["scope"][0].split()
    assert query["redirect_uri"] == ["https://api.esempio.it/oauth/google/callback"]


def test_authorization_url_requires_configuration() -> None:
    with pytest.raises(GoogleNotConfiguredError):
        build_service(FakeGoogle(), FakeAdminStore(), client_id="").authorization_url(TENANT.id, USER)
    with pytest.raises(GoogleNotConfiguredError):
        build_service(FakeGoogle(), FakeAdminStore(), encryption_key="").authorization_url(
            TENANT.id, USER
        )


def test_complete_authorization_stores_encrypted_refresh_token() -> None:
    google, admin, _ = connected_setup()
    stored = admin.credentials[TENANT.id]
    assert stored.google_account_email == "salone@example.com"
    assert stored.calendar_id == "primary"
    assert "refresh-1" not in stored.refresh_token_encrypted
    assert TokenCipher(TEST_KEY).decrypt(stored.refresh_token_encrypted) == "refresh-1"
    exchange = next(body for m, url, body in google.calls if body.get("grant_type") == "authorization_code")
    assert exchange["code"] == "auth-code"


@pytest.mark.parametrize(
    ("setup", "expected_code"),
    [
        ("tampered_state", "invalid_state"),
        ("not_member", "forbidden"),
        ("missing_scopes", "missing_scopes"),
        ("no_refresh_token", "no_refresh_token"),
    ],
)
def test_complete_authorization_failures(setup: str, expected_code: str) -> None:
    google = FakeGoogle()
    admin = FakeAdminStore(set() if setup == "not_member" else {(TENANT.id, USER)})
    service = build_service(google, admin)
    state = parse_qs(urlparse(service.authorization_url(TENANT.id, USER)).query)["state"][0]
    if setup == "tampered_state":
        state = state[:-6] + "AAAAAA"
    if setup == "missing_scopes":
        google.granted_scope = f"openid email {CALENDAR_EVENTS_SCOPE}"
    if setup == "no_refresh_token":
        google.give_refresh_token = False

    with pytest.raises(OAuthFlowError) as exc_info:
        asyncio.run(service.complete_authorization("auth-code", state))
    assert exc_info.value.code == expected_code
    assert TENANT.id not in admin.credentials


def test_state_from_other_installation_is_rejected() -> None:
    service = build_service(FakeGoogle(), FakeAdminStore({(TENANT.id, USER)}))
    foreign = build_service(FakeGoogle(), FakeAdminStore(), encryption_key=Fernet.generate_key().decode())
    state = parse_qs(urlparse(foreign.authorization_url(TENANT.id, USER)).query)["state"][0]
    with pytest.raises(OAuthFlowError, match="scaduta o non valida"):
        asyncio.run(service.complete_authorization("auth-code", state))


def test_status_and_disconnect_revokes_token() -> None:
    google, admin, events = connected_setup()
    service = build_service(google, admin, events)
    status = asyncio.run(service.status(TENANT.id))
    assert status.connected and status.google_account_email == "salone@example.com"

    asyncio.run(service.disconnect(TENANT.id))
    assert not asyncio.run(service.status(TENANT.id)).connected
    revoke = [body for m, url, body in google.calls if url.endswith("/revoke")]
    assert revoke == [{"token": "refresh-1"}]


# ------------------------------------------------------- uso del calendario


def test_busy_intervals_empty_when_not_connected() -> None:
    google = FakeGoogle()
    service = build_service(google, FakeAdminStore())
    now = datetime(2026, 11, 5, 10, tzinfo=ROME)
    assert asyncio.run(service.busy_intervals(TENANT.id, now, now + timedelta(days=1))) == []
    assert google.calls == []


def test_busy_intervals_reads_freebusy_and_caches_token() -> None:
    google, admin, events = connected_setup()
    service = build_service(google, admin, events)  # nuova istanza: cache vuota
    start = datetime(2026, 11, 6, 15, tzinfo=ROME)
    google.busy = [(start, start + timedelta(hours=1))]

    window = (start - timedelta(hours=6), start + timedelta(hours=6))
    first = asyncio.run(service.busy_intervals(TENANT.id, *window))
    asyncio.run(service.busy_intervals(TENANT.id, *window))

    assert first == [(start, start + timedelta(hours=1))]
    assert google.refresh_count == 1  # il secondo accesso usa il token in cache
    freebusy = [body for m, url, body in google.calls if url.endswith("/freeBusy")]
    assert freebusy[0]["items"] == [{"id": "primary"}]


def test_busy_intervals_fail_closed_when_google_down() -> None:
    google, admin, events = connected_setup()
    google.fail_calendar = True
    service = build_service(google, admin, events)
    now = datetime(2026, 11, 5, 10, tzinfo=ROME)
    with pytest.raises(CalendarUnavailableError):
        asyncio.run(service.busy_intervals(TENANT.id, now, now + timedelta(days=1)))


def test_busy_intervals_fail_closed_when_access_revoked() -> None:
    google, admin, events = connected_setup()
    google.revoked_refresh_tokens.add("refresh-1")
    service = build_service(google, admin, events)
    now = datetime(2026, 11, 5, 10, tzinfo=ROME)
    with pytest.raises(CalendarUnavailableError):
        asyncio.run(service.busy_intervals(TENANT.id, now, now + timedelta(days=1)))


def conversation() -> Conversation:
    return Conversation(
        id=uuid4(), tenant_id=TENANT.id, customer_phone="+393331112222", customer_name="Mario",
        state=ConversationState.COMPLETED, mode=ConversationMode.AI, failed_attempts=0,
    )


def test_booking_creates_event_and_links_it() -> None:
    google, admin, events = connected_setup()
    service = build_service(google, admin, events)
    booking_id = uuid4()
    start = datetime(2026, 11, 6, 15, tzinfo=ROME)
    asyncio.run(service.on_booking_confirmed(
        TENANT, conversation(), make_service(TENANT.id, "Taglio uomo", 30, 2000),
        booking_id, start, start + timedelta(minutes=30),
    ))
    [event] = google.events
    assert event["summary"] == "Taglio uomo - Mario"
    assert "+393331112222" in event["description"]
    assert event["start"] == {"dateTime": "2026-11-06T15:00:00+01:00", "timeZone": "Europe/Rome"}
    assert event["extendedProperties"]["private"]["booking_id"] == str(booking_id)
    assert events.linked == [(TENANT.id, booking_id, "evt-1")]


def test_booking_event_failure_never_raises() -> None:
    google, admin, events = connected_setup()
    google.fail_calendar = True
    service = build_service(google, admin, events)
    start = datetime(2026, 11, 6, 15, tzinfo=ROME)
    asyncio.run(service.on_booking_confirmed(
        TENANT, conversation(), make_service(TENANT.id, "Piega", 30, 2500),
        uuid4(), start, start + timedelta(minutes=30),
    ))
    assert events.linked == []


def test_booking_without_calendar_does_nothing() -> None:
    google = FakeGoogle()
    service = build_service(google, FakeAdminStore())
    start = datetime(2026, 11, 6, 15, tzinfo=ROME)
    asyncio.run(service.on_booking_confirmed(
        TENANT, conversation(), make_service(TENANT.id, "Piega", 30, 2500),
        uuid4(), start, start + timedelta(minutes=30),
    ))
    assert google.calls == []


# ------------------------------------------------- flusso di sviluppo (simulatore)


def state_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


def test_dev_flow_disabled_by_default() -> None:
    with pytest.raises(OAuthFlowError) as exc_info:
        build_service(FakeGoogle(), FakeAdminStore()).dev_authorization_url(TENANT.id)
    assert exc_info.value.code == "dev_disabled"


def test_dev_flow_connects_without_user_and_returns_to_simulator() -> None:
    admin = FakeAdminStore()  # nessun membro: il flusso dev non lo richiede
    service = build_service(FakeGoogle(), admin, allow_dev_flow=True)
    state = state_of(service.dev_authorization_url(TENANT.id))

    assert service.return_target(state) == "simulator"
    result = asyncio.run(service.complete_authorization("auth-code", state))
    assert result.tenant_id == TENANT.id and result.return_to == "simulator"
    assert TENANT.id in admin.credentials


def test_dev_state_rejected_when_dev_flow_disabled() -> None:
    """Uno state "dev" (stessa chiave) non deve funzionare in produzione."""
    dev = build_service(FakeGoogle(), FakeAdminStore(), allow_dev_flow=True)
    state = state_of(dev.dev_authorization_url(TENANT.id))
    production = build_service(FakeGoogle(), FakeAdminStore())

    assert production.return_target(state) == "dashboard"
    with pytest.raises(OAuthFlowError) as exc_info:
        asyncio.run(production.complete_authorization("auth-code", state))
    assert exc_info.value.code == "invalid_state"


def test_dashboard_flow_returns_to_dashboard() -> None:
    service = build_service(FakeGoogle(), FakeAdminStore({(TENANT.id, USER)}), allow_dev_flow=True)
    state = state_of(service.authorization_url(TENANT.id, USER))
    assert service.return_target(state) == "dashboard"
    assert service.return_target("spazzatura") == "dashboard"
    assert service.return_target(None) == "dashboard"
    assert asyncio.run(service.complete_authorization("auth-code", state)).return_to == "dashboard"
