"""Finto server Google (OAuth + Calendar API) basato su httpx.MockTransport."""

import json
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

import httpx
from cryptography.fernet import Fernet

from backend.app.models.schemas import GoogleCredentials
from backend.app.services.calendar.google_calendar import GoogleCalendarService
from backend.app.services.calendar.google_client import (
    CALENDAR_EVENTS_SCOPE,
    CALENDAR_FREEBUSY_SCOPE,
    GoogleCalendarClient,
)

FULL_SCOPE = f"openid email {CALENDAR_EVENTS_SCOPE} {CALENDAR_FREEBUSY_SCOPE}"
TEST_KEY = Fernet.generate_key().decode()


class FakeGoogle:
    def __init__(self) -> None:
        self.busy: list[tuple[datetime, datetime]] = []
        self.granted_scope = FULL_SCOPE
        self.give_refresh_token = True
        self.revoked_refresh_tokens: set[str] = set()
        self.fail_calendar = False
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.events: list[dict[str, Any]] = []
        self._refresh_count = 0

    @property
    def refresh_count(self) -> int:
        return self._refresh_count

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        body: dict[str, Any]
        if request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content or b"{}")
        else:
            body = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.calls.append((request.method, url, body))

        if url == "https://oauth2.googleapis.com/token":
            return self._token(body)
        if url == "https://oauth2.googleapis.com/revoke":
            return httpx.Response(200)
        if url == "https://openidconnect.googleapis.com/v1/userinfo":
            return httpx.Response(200, json={"email": "salone@example.com"})
        if self.fail_calendar:
            return httpx.Response(503, text="backend error")
        if url.endswith("/freeBusy"):
            cal = body["items"][0]["id"]
            busy = [{"start": s.isoformat(), "end": e.isoformat()} for s, e in self.busy]
            return httpx.Response(200, json={"calendars": {cal: {"busy": busy}}})
        if url.endswith("/events"):
            self.events.append(body)
            return httpx.Response(200, json={"id": f"evt-{len(self.events)}"})
        return httpx.Response(404, text=f"not mocked: {url}")

    def _token(self, body: dict[str, Any]) -> httpx.Response:
        if body.get("grant_type") == "authorization_code":
            payload: dict[str, Any] = {
                "access_token": "access-from-code",
                "expires_in": 3599,
                "scope": self.granted_scope,
            }
            if self.give_refresh_token:
                payload["refresh_token"] = "refresh-1"
            return httpx.Response(200, json=payload)
        if body.get("refresh_token") in self.revoked_refresh_tokens:
            return httpx.Response(400, json={"error": "invalid_grant"})
        self._refresh_count += 1
        return httpx.Response(
            200,
            json={"access_token": f"access-{self._refresh_count}", "expires_in": 3599, "scope": self.granted_scope},
        )


class FakeAdminStore:
    def __init__(self, members: set[tuple[UUID, UUID]] | None = None) -> None:
        self.members = members or set()
        self.credentials: dict[UUID, GoogleCredentials] = {}

    async def is_tenant_member(self, tenant_id: UUID, user_id: UUID) -> bool:
        return (tenant_id, user_id) in self.members

    async def get_google_credentials(self, tenant_id: UUID) -> GoogleCredentials | None:
        return self.credentials.get(tenant_id)

    async def save_google_credentials(self, credentials: GoogleCredentials) -> None:
        self.credentials[credentials.tenant_id] = credentials

    async def delete_google_credentials(self, tenant_id: UUID) -> None:
        self.credentials.pop(tenant_id, None)


class FakeBookingEvents:
    def __init__(self) -> None:
        self.linked: list[tuple[UUID, UUID, str]] = []

    async def set_booking_google_event(
        self, tenant_id: UUID, booking_id: UUID, google_event_id: str
    ) -> None:
        self.linked.append((tenant_id, booking_id, google_event_id))


def build_service(
    google: FakeGoogle,
    admin: FakeAdminStore,
    events: FakeBookingEvents | None = None,
    *,
    client_id: str = "client-id",
    encryption_key: str = TEST_KEY,
) -> GoogleCalendarService:
    client = GoogleCalendarClient(
        client_id=client_id,
        client_secret="client-secret",
        redirect_uri="https://api.esempio.it/oauth/google/callback",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(google.handler)),
    )
    return GoogleCalendarService(
        client=client,
        admin_store=admin,
        booking_store=events or FakeBookingEvents(),
        encryption_key=encryption_key,
    )
