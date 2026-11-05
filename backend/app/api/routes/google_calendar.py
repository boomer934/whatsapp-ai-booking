"""Collegamento di Google Calendar dalla dashboard (OAuth 2.0 per tenant)."""

import logging
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from backend.app.api.auth import AuthenticatedUser, require_tenant_member
from backend.app.api.deps import get_google_calendar_service
from backend.app.core.config import Settings, get_settings
from backend.app.services.calendar.google_calendar import (
    GoogleCalendarService,
    GoogleConnectionStatus,
    GoogleNotConfiguredError,
    OAuthFlowError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["google-calendar"])

MemberDep = Annotated[AuthenticatedUser, Depends(require_tenant_member)]
CalendarDep = Annotated[GoogleCalendarService, Depends(get_google_calendar_service)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Pagina della dashboard a cui tornare dopo il consenso Google.
DASHBOARD_RETURN_PATH = "/dashboard/settings"
SIMULATOR_RETURN_PATH = "/simulator"


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str


@router.get("/api/tenants/{tenant_id}/google", response_model=GoogleConnectionStatus)
async def google_status(
    tenant_id: UUID, _user: MemberDep, calendar: CalendarDep
) -> GoogleConnectionStatus:
    return await calendar.status(tenant_id)


@router.post(
    "/api/tenants/{tenant_id}/google/connect", response_model=AuthorizationUrlResponse
)
async def google_connect(
    tenant_id: UUID, user: MemberDep, calendar: CalendarDep
) -> AuthorizationUrlResponse:
    """Restituisce l'URL di consenso Google verso cui la dashboard reindirizza l'utente."""
    try:
        url = calendar.authorization_url(tenant_id, user.id)
    except GoogleNotConfiguredError as exc:
        logger.error("Collegamento Google non configurato: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Integrazione Google non configurata"
        ) from exc
    return AuthorizationUrlResponse(authorization_url=url)


@router.delete("/api/tenants/{tenant_id}/google", status_code=status.HTTP_204_NO_CONTENT)
async def google_disconnect(tenant_id: UUID, _user: MemberDep, calendar: CalendarDep) -> Response:
    await calendar.disconnect(tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/oauth/google/callback", include_in_schema=False)
async def google_callback(
    calendar: CalendarDep,
    settings: SettingsDep,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Callback pubblico di Google: l'identità è garantita dallo `state` cifrato."""
    target = calendar.return_target(state)

    def back(**params: str) -> RedirectResponse:
        if target == "simulator":
            base = SIMULATOR_RETURN_PATH  # stesso backend: percorso relativo
        else:
            base = settings.frontend_url.rstrip("/") + DASHBOARD_RETURN_PATH
        return RedirectResponse(f"{base}?{urlencode(params)}", status_code=status.HTTP_302_FOUND)

    if error or not code or not state:
        return back(google="error", reason=error or "missing_code")
    try:
        await calendar.complete_authorization(code, state)
    except OAuthFlowError as exc:
        logger.warning("Collegamento Google fallito (%s): %s", exc.code, exc)
        return back(google="error", reason=exc.code)
    except GoogleNotConfiguredError:
        return back(google="error", reason="not_configured")
    return back(google="connected")
