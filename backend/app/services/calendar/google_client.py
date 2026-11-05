"""Client HTTP minimale per OAuth Google e Google Calendar API v3 (senza SDK)."""

from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from pydantic import BaseModel

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"

CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.freebusy"
# Minimo indispensabile: leggere gli orari occupati e creare eventi.
SCOPES = ("openid", "email", CALENDAR_EVENTS_SCOPE, CALENDAR_FREEBUSY_SCOPE)
REQUIRED_SCOPES = frozenset({CALENDAR_EVENTS_SCOPE, CALENDAR_FREEBUSY_SCOPE})


class GoogleApiError(RuntimeError):
    """Errore di rete o risposta di errore dalle API Google."""


class GoogleAuthRevokedError(GoogleApiError):
    """Il refresh token non è più valido (accesso revocato dall'utente)."""


class TokenResponse(BaseModel):
    access_token: str
    expires_in: int = 3600
    refresh_token: str | None = None
    scope: str = ""

    @property
    def scopes(self) -> set[str]:
        return set(self.scope.split())


class GoogleCalendarClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout
        self._http_client = http_client

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            # offline + consent: Google restituisce sempre un refresh token.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params, quote_via=quote)}"

    async def exchange_code(self, code: str) -> TokenResponse:
        data = await self._request(
            "POST",
            TOKEN_URL,
            data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        return TokenResponse.model_validate(data)

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        data = await self._request(
            "POST",
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            },
        )
        return TokenResponse.model_validate(data)

    async def get_user_email(self, access_token: str) -> str | None:
        data = await self._request("GET", USERINFO_URL, access_token=access_token)
        email = data.get("email")
        return email if isinstance(email, str) else None

    async def free_busy(
        self, access_token: str, calendar_id: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        data = await self._request(
            "POST",
            f"{CALENDAR_API}/freeBusy",
            access_token=access_token,
            json={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": calendar_id}],
            },
        )
        calendar = data.get("calendars", {}).get(calendar_id, {})
        if calendar.get("errors"):
            raise GoogleApiError(f"Errore free/busy sul calendario: {calendar['errors']}")
        return [
            (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in calendar.get("busy", [])
        ]

    async def create_event(
        self,
        access_token: str,
        calendar_id: str,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        timezone: str,
        booking_id: str,
    ) -> str:
        data = await self._request(
            "POST",
            f"{CALENDAR_API}/calendars/{quote(calendar_id, safe='')}/events",
            access_token=access_token,
            json={
                "summary": summary,
                "description": description,
                "start": {"dateTime": start.isoformat(), "timeZone": timezone},
                "end": {"dateTime": end.isoformat(), "timeZone": timezone},
                "extendedProperties": {"private": {"booking_id": booking_id}},
            },
        )
        event_id = data.get("id")
        if not isinstance(event_id, str):
            raise GoogleApiError("Risposta di creazione evento senza id.")
        return event_id

    async def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
        """Elimina un evento. Un evento già eliminato (404/410) non è un errore."""
        url = (
            f"{CALENDAR_API}/calendars/{quote(calendar_id, safe='')}"
            f"/events/{quote(event_id, safe='')}"
        )
        try:
            await self._request("DELETE", url, access_token=access_token)
        except GoogleApiError as exc:
            if " 404:" in str(exc) or " 410:" in str(exc):
                return
            raise

    async def revoke(self, token: str) -> None:
        await self._request("POST", REVOKE_URL, data={"token": token})

    async def _request(
        self,
        method: str,
        url: str,
        *,
        access_token: str | None = None,
        data: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.request(method, url, headers=headers, data=data, json=json)
        except httpx.HTTPError as exc:
            raise GoogleApiError(f"Google non raggiungibile: {type(exc).__name__} {exc}") from exc
        finally:
            if self._http_client is None:
                await client.aclose()

        if response.is_error:
            if response.status_code in (400, 401) and "invalid_grant" in response.text:
                raise GoogleAuthRevokedError("Accesso a Google Calendar revocato o scaduto.")
            raise GoogleApiError(f"Google API {response.status_code}: {response.text[:300]}")
        if not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise GoogleApiError("Risposta Google non è JSON valido.") from exc
        return body if isinstance(body, dict) else {}
