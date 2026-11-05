"""Integrazione Google Calendar per tenant: collegamento OAuth, free/busy, eventi.

Regola di sicurezza sulla disponibilità: se il tenant ha collegato un calendario
ma Google non risponde, solleviamo CalendarUnavailableError (fail-closed) invece
di proporre orari che potrebbero sovrapporsi agli impegni del titolare.
"""

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from backend.app.core.crypto import CryptoConfigError, InvalidEncryptedValue, TokenCipher
from backend.app.models.schemas import Conversation, GoogleCredentials, Service, Tenant
from backend.app.repositories.tenant_admin import TenantAdminStore
from backend.app.services.calendar.availability import CalendarUnavailableError, Interval
from backend.app.services.calendar.google_client import (
    REQUIRED_SCOPES,
    GoogleApiError,
    GoogleCalendarClient,
)

logger = logging.getLogger(__name__)

OAUTH_STATE_TTL_SECONDS = 600
TOKEN_EXPIRY_MARGIN = timedelta(seconds=60)


class GoogleNotConfiguredError(RuntimeError):
    """GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / ENCRYPTION_KEY mancanti."""


class OAuthFlowError(RuntimeError):
    """Il collegamento non è andato a buon fine. `code` è mostrabile alla dashboard."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# Dove riportare l'utente dopo il consenso Google.
ReturnTarget = Literal["dashboard", "simulator"]


class AuthorizationResult(BaseModel):
    tenant_id: UUID
    return_to: ReturnTarget


class GoogleConnectionStatus(BaseModel):
    connected: bool
    google_account_email: str | None = None
    calendar_id: str | None = None


class BookingEventStore(Protocol):
    """Sottoinsieme dello store necessario per collegare evento e prenotazione."""

    async def set_booking_google_event(
        self, tenant_id: UUID, booking_id: UUID, google_event_id: str
    ) -> None: ...


@dataclass
class _CachedToken:
    access_token: str
    expires_at: datetime


class GoogleCalendarService:
    def __init__(
        self,
        client: GoogleCalendarClient,
        admin_store: TenantAdminStore,
        booking_store: BookingEventStore,
        encryption_key: str,
        allow_dev_flow: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client
        # Collegamento dal simulatore locale senza utente autenticato: solo sviluppo.
        self._allow_dev_flow = allow_dev_flow
        self._admin_store = admin_store
        self._booking_store = booking_store
        self._encryption_key = encryption_key
        self._clock = clock
        self._tokens: dict[UUID, _CachedToken] = {}

    # ------------------------------------------------------------ collegamento

    def _cipher(self) -> TokenCipher:
        try:
            return TokenCipher(self._encryption_key)
        except CryptoConfigError as exc:
            raise GoogleNotConfiguredError(str(exc)) from exc

    def authorization_url(self, tenant_id: UUID, user_id: UUID) -> str:
        """URL di consenso per un membro autenticato del tenant (dashboard)."""
        return self._build_authorization_url(
            {"t": str(tenant_id), "u": str(user_id), "r": "dashboard"}
        )

    def dev_authorization_url(self, tenant_id: UUID) -> str:
        """URL di consenso dal simulatore locale (nessun utente: solo sviluppo)."""
        if not self._allow_dev_flow:
            raise OAuthFlowError("dev_disabled", "Collegamento di sviluppo non consentito.")
        return self._build_authorization_url({"t": str(tenant_id), "dev": True, "r": "simulator"})

    def _build_authorization_url(self, payload: dict[str, object]) -> str:
        if not self._client.is_configured:
            raise GoogleNotConfiguredError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET mancanti.")
        state = self._cipher().encrypt_json({**payload, "n": secrets.token_urlsafe(8)})
        return self._client.authorization_url(state)

    def return_target(self, state: str | None) -> ReturnTarget:
        """Dove tornare dopo il callback (anche in caso di errore o consenso negato)."""
        if not state:
            return "dashboard"
        try:
            payload = self._cipher().decrypt_json(state)
        except (InvalidEncryptedValue, GoogleNotConfiguredError, ValueError):
            return "dashboard"
        if payload.get("r") == "simulator" and self._allow_dev_flow:
            return "simulator"
        return "dashboard"

    async def complete_authorization(self, code: str, state: str) -> AuthorizationResult:
        """Gestisce il callback OAuth e salva il collegamento del tenant."""
        cipher = self._cipher()
        try:
            payload = cipher.decrypt_json(state, ttl_seconds=OAUTH_STATE_TTL_SECONDS)
            tenant_id = UUID(payload["t"])
            dev_flow = payload.get("dev") is True
            user_id = None if dev_flow else UUID(payload["u"])
        except (InvalidEncryptedValue, KeyError, ValueError) as exc:
            raise OAuthFlowError("invalid_state", "Richiesta scaduta o non valida.") from exc

        if dev_flow:
            if not self._allow_dev_flow:
                raise OAuthFlowError("invalid_state", "Collegamento di sviluppo non consentito.")
        elif user_id is None or not await self._admin_store.is_tenant_member(tenant_id, user_id):
            raise OAuthFlowError("forbidden", "Utente non autorizzato per questa attività.")

        try:
            tokens = await self._client.exchange_code(code)
        except GoogleApiError as exc:
            raise OAuthFlowError("exchange_failed", str(exc)) from exc
        if not REQUIRED_SCOPES <= tokens.scopes:
            raise OAuthFlowError(
                "missing_scopes",
                "Servono i permessi per vedere la disponibilità e creare eventi.",
            )
        if not tokens.refresh_token:
            raise OAuthFlowError("no_refresh_token", "Google non ha fornito un refresh token.")

        try:
            email = await self._client.get_user_email(tokens.access_token)
        except GoogleApiError:
            logger.warning("Email dell'account Google non disponibile per %s", tenant_id)
            email = None

        await self._admin_store.save_google_credentials(
            GoogleCredentials(
                tenant_id=tenant_id,
                google_account_email=email,
                refresh_token_encrypted=cipher.encrypt(tokens.refresh_token),
            )
        )
        self._cache_token(tenant_id, tokens.access_token, tokens.expires_in)
        logger.info("Google Calendar collegato per il tenant %s", tenant_id)
        return AuthorizationResult(
            tenant_id=tenant_id, return_to="simulator" if dev_flow else "dashboard"
        )

    async def status(self, tenant_id: UUID) -> GoogleConnectionStatus:
        credentials = await self._admin_store.get_google_credentials(tenant_id)
        if credentials is None:
            return GoogleConnectionStatus(connected=False)
        return GoogleConnectionStatus(
            connected=True,
            google_account_email=credentials.google_account_email,
            calendar_id=credentials.calendar_id,
        )

    async def disconnect(self, tenant_id: UUID) -> None:
        credentials = await self._admin_store.get_google_credentials(tenant_id)
        if credentials is None:
            return
        try:
            refresh_token = self._cipher().decrypt(credentials.refresh_token_encrypted)
            await self._client.revoke(refresh_token)
        except (GoogleApiError, GoogleNotConfiguredError, InvalidEncryptedValue):
            logger.warning("Revoca del token Google non riuscita per %s", tenant_id)
        await self._admin_store.delete_google_credentials(tenant_id)
        self._tokens.pop(tenant_id, None)

    # ----------------------------------------------------- uso del calendario

    async def busy_intervals(
        self, tenant_id: UUID, start: datetime, end: datetime
    ) -> list[Interval]:
        """Intervalli occupati su Google. [] se il tenant non ha collegato un calendario."""
        credentials = await self._admin_store.get_google_credentials(tenant_id)
        if credentials is None:
            return []
        try:
            token = await self._access_token(credentials)
            return await self._client.free_busy(token, credentials.calendar_id, start, end)
        except (GoogleApiError, GoogleNotConfiguredError, InvalidEncryptedValue) as exc:
            logger.error("Google Calendar non disponibile per %s: %s", tenant_id, exc)
            raise CalendarUnavailableError(str(exc)) from exc

    async def on_booking_confirmed(
        self,
        tenant: Tenant,
        conversation: Conversation,
        service: Service,
        booking_id: UUID,
        start: datetime,
        end: datetime,
    ) -> None:
        """Crea l'evento sul calendario. Non solleva mai: la prenotazione nel DB
        resta valida anche se Google non risponde."""
        try:
            credentials = await self._admin_store.get_google_credentials(tenant.id)
            if credentials is None:
                return
            token = await self._access_token(credentials)
            customer = conversation.customer_name or conversation.customer_phone
            event_id = await self._client.create_event(
                token,
                credentials.calendar_id,
                summary=f"{service.name} - {customer}",
                description=(
                    "Prenotazione da WhatsApp\n"
                    f"Cliente: {conversation.customer_name or '-'}\n"
                    f"Telefono: {conversation.customer_phone}"
                ),
                start=start,
                end=end,
                timezone=tenant.timezone,
                booking_id=str(booking_id),
            )
            await self._booking_store.set_booking_google_event(tenant.id, booking_id, event_id)
        except Exception:
            logger.exception("Creazione evento Google fallita per la prenotazione %s", booking_id)

    async def on_booking_cancelled(self, tenant_id: UUID, google_event_id: str) -> bool:
        """Rimuove l'evento della prenotazione annullata. Non solleva mai.
        Restituisce True se l'evento è stato rimosso (o non esisteva più)."""
        try:
            credentials = await self._admin_store.get_google_credentials(tenant_id)
            if credentials is None:
                return False
            token = await self._access_token(credentials)
            await self._client.delete_event(token, credentials.calendar_id, google_event_id)
            return True
        except Exception:
            logger.exception("Rimozione evento Google %s fallita", google_event_id)
            return False

    # ---------------------------------------------------------------- token

    async def _access_token(self, credentials: GoogleCredentials) -> str:
        cached = self._tokens.get(credentials.tenant_id)
        if cached and cached.expires_at - TOKEN_EXPIRY_MARGIN > self._clock():
            return cached.access_token
        refresh_token = self._cipher().decrypt(credentials.refresh_token_encrypted)
        tokens = await self._client.refresh_access_token(refresh_token)
        self._cache_token(credentials.tenant_id, tokens.access_token, tokens.expires_in)
        return tokens.access_token

    def _cache_token(self, tenant_id: UUID, access_token: str, expires_in: int) -> None:
        self._tokens[tenant_id] = _CachedToken(
            access_token=access_token,
            expires_at=self._clock() + timedelta(seconds=expires_in),
        )
