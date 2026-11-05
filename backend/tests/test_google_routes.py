"""Test degli endpoint di collegamento Google Calendar (auth e callback OAuth)."""

from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.api.auth import AuthenticatedUser, get_admin_store, get_auth_verifier
from backend.app.api.deps import get_google_calendar_service
from backend.app.core.config import Settings, get_settings
from backend.main import app
from backend.tests.google_fake import FakeAdminStore, FakeGoogle, build_service

TENANT_A = uuid4()
TENANT_B = uuid4()
USER = uuid4()
GOOD = {"Authorization": "Bearer token-valido"}


class FakeVerifier:
    async def verify(self, access_token: str) -> AuthenticatedUser | None:
        return AuthenticatedUser(id=USER, email="titolare@example.com") if access_token == "token-valido" else None


class Env:
    def __init__(self) -> None:
        self.google = FakeGoogle()
        self.admin = FakeAdminStore({(TENANT_A, USER)})
        self.calendar = build_service(self.google, self.admin)
        self.client = TestClient(app, follow_redirects=False)


@pytest.fixture
def env() -> Iterator[Env]:
    e = Env()
    app.dependency_overrides[get_auth_verifier] = lambda: FakeVerifier()
    app.dependency_overrides[get_admin_store] = lambda: e.admin
    app.dependency_overrides[get_google_calendar_service] = lambda: e.calendar
    app.dependency_overrides[get_settings] = lambda: Settings(
        frontend_url="https://app.esempio.it", _env_file=None  # type: ignore[call-arg]
    )
    yield e
    app.dependency_overrides.clear()


def connect_url(env: Env, tenant: UUID = TENANT_A) -> str:
    response = env.client.post(f"/api/tenants/{tenant}/google/connect", headers=GOOD)
    assert response.status_code == 200
    url: str = response.json()["authorization_url"]
    return url


# ------------------------------------------------------------ autorizzazione


def test_requires_bearer_token(env: Env) -> None:
    assert env.client.get(f"/api/tenants/{TENANT_A}/google").status_code == 401
    bad = {"Authorization": "Bearer scaduto"}
    assert env.client.get(f"/api/tenants/{TENANT_A}/google", headers=bad).status_code == 401
    assert env.client.get(f"/api/tenants/{TENANT_A}/google", headers={"Authorization": "token-valido"}).status_code == 401


def test_member_of_other_tenant_is_forbidden(env: Env) -> None:
    for method, path in [
        ("GET", f"/api/tenants/{TENANT_B}/google"),
        ("POST", f"/api/tenants/{TENANT_B}/google/connect"),
        ("DELETE", f"/api/tenants/{TENANT_B}/google"),
    ]:
        assert env.client.request(method, path, headers=GOOD).status_code == 403


# ----------------------------------------------------------- flusso completo


def test_full_connect_flow_and_disconnect(env: Env) -> None:
    status = env.client.get(f"/api/tenants/{TENANT_A}/google", headers=GOOD).json()
    assert status == {"connected": False, "google_account_email": None, "calendar_id": None}

    url = connect_url(env)
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    state = parse_qs(urlparse(url).query)["state"][0]

    # Google reindirizza il browser al callback con code e state.
    callback = env.client.get("/oauth/google/callback", params={"code": "auth-code", "state": state})
    assert callback.status_code == 302
    assert callback.headers["location"] == "https://app.esempio.it/dashboard/settings?google=connected"

    status = env.client.get(f"/api/tenants/{TENANT_A}/google", headers=GOOD).json()
    assert status == {"connected": True, "google_account_email": "salone@example.com", "calendar_id": "primary"}

    assert env.client.delete(f"/api/tenants/{TENANT_A}/google", headers=GOOD).status_code == 204
    assert env.client.get(f"/api/tenants/{TENANT_A}/google", headers=GOOD).json()["connected"] is False


@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({"error": "access_denied"}, "access_denied"),
        ({"code": "x"}, "missing_code"),
        ({"code": "x", "state": "manomesso"}, "invalid_state"),
    ],
)
def test_callback_errors_redirect_to_dashboard(env: Env, params: dict[str, str], reason: str) -> None:
    response = env.client.get("/oauth/google/callback", params=params)
    assert response.status_code == 302
    assert response.headers["location"] == (
        f"https://app.esempio.it/dashboard/settings?google=error&reason={reason}"
    )
    assert env.admin.credentials == {}


def test_callback_rejects_user_removed_from_tenant(env: Env) -> None:
    state = parse_qs(urlparse(connect_url(env)).query)["state"][0]
    env.admin.members.clear()  # l'utente perde l'accesso prima di completare il consenso
    response = env.client.get("/oauth/google/callback", params={"code": "auth-code", "state": state})
    assert response.headers["location"].endswith("google=error&reason=forbidden")
    assert env.admin.credentials == {}


def test_connect_returns_503_when_google_not_configured(env: Env) -> None:
    app.dependency_overrides[get_google_calendar_service] = lambda: build_service(
        env.google, env.admin, client_id=""
    )
    response = env.client.post(f"/api/tenants/{TENANT_A}/google/connect", headers=GOOD)
    assert response.status_code == 503


# ------------------------------------------------------- annullamento prenotazioni


def connect(env: Env) -> None:
    state = parse_qs(urlparse(connect_url(env)).query)["state"][0]
    env.client.get("/oauth/google/callback", params={"code": "auth-code", "state": state})


def add_booking(env: Env, event_id: str | None = "evt-42") -> UUID:
    from backend.app.models.enums import BookingStatus
    from backend.app.repositories.tenant_admin import BookingRef

    booking_id = uuid4()
    env.admin.bookings[(TENANT_A, booking_id)] = BookingRef(
        id=booking_id, status=BookingStatus.CONFIRMED, google_event_id=event_id
    )
    return booking_id


def test_cancel_booking_removes_google_event(env: Env) -> None:
    connect(env)
    booking_id = add_booking(env)
    response = env.client.post(f"/api/tenants/{TENANT_A}/bookings/{booking_id}/cancel", headers=GOOD)
    assert response.status_code == 200
    assert response.json() == {"status": "cancelled", "google_event_removed": True}
    assert env.admin.bookings[(TENANT_A, booking_id)].status == "cancelled"
    assert env.google.deleted_events == ["evt-42"]


def test_cancel_booking_event_already_deleted_on_google(env: Env) -> None:
    connect(env)
    env.google.missing_events.add("evt-42")
    booking_id = add_booking(env)
    response = env.client.post(f"/api/tenants/{TENANT_A}/bookings/{booking_id}/cancel", headers=GOOD)
    assert response.json() == {"status": "cancelled", "google_event_removed": True}


def test_cancel_booking_without_calendar_or_event(env: Env) -> None:
    booking_id = add_booking(env, event_id=None)
    response = env.client.post(f"/api/tenants/{TENANT_A}/bookings/{booking_id}/cancel", headers=GOOD)
    assert response.json() == {"status": "cancelled", "google_event_removed": False}


def test_cancel_booking_google_down_still_cancels(env: Env) -> None:
    connect(env)
    env.google.fail_calendar = True
    booking_id = add_booking(env)
    response = env.client.post(f"/api/tenants/{TENANT_A}/bookings/{booking_id}/cancel", headers=GOOD)
    assert response.json() == {"status": "cancelled", "google_event_removed": False}
    assert env.admin.bookings[(TENANT_A, booking_id)].status == "cancelled"


def test_cancel_booking_authorization(env: Env) -> None:
    booking_id = add_booking(env)
    assert env.client.post(f"/api/tenants/{TENANT_A}/bookings/{booking_id}/cancel").status_code == 401
    assert env.client.post(f"/api/tenants/{TENANT_B}/bookings/{booking_id}/cancel", headers=GOOD).status_code == 403
    assert env.client.post(f"/api/tenants/{TENANT_A}/bookings/{uuid4()}/cancel", headers=GOOD).status_code == 404
