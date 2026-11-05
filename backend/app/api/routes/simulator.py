"""Simulatore WhatsApp locale (solo sviluppo, solo da localhost).

Registrato in main.py solo se `settings.simulator_active` (mai in production).
"""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.api.deps import get_google_calendar_service, get_simulator_service
from backend.app.services.calendar.google_calendar import (
    GoogleCalendarService,
    GoogleConnectionStatus,
    GoogleNotConfiguredError,
    OAuthFlowError,
)
from backend.app.simulator.service import SimulatorService, SimulatorSnapshot, SimulatorTurn
from backend.app.simulator.store import TenantSummary

STATIC_PAGE = Path(__file__).resolve().parents[2] / "simulator" / "static" / "index.html"
LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
# Header aggiunti da proxy e tunnel (cloudflared, ngrok, Render): la richiesta non è locale.
PROXY_HEADERS = ("x-forwarded-for", "cf-connecting-ip", "forwarded", "x-real-ip")


def require_local_request(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS or any(h in request.headers for h in PROXY_HEADERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Simulatore disponibile solo in locale")


router = APIRouter(
    prefix="/simulator",
    tags=["simulator"],
    include_in_schema=False,
    dependencies=[Depends(require_local_request)],
)

ServiceDep = Annotated[SimulatorService, Depends(get_simulator_service)]
CalendarDep = Annotated[GoogleCalendarService, Depends(get_google_calendar_service)]


class SendRequest(BaseModel):
    tenant_id: UUID
    phone: str = Field(min_length=6, max_length=20)
    name: str | None = Field(default=None, max_length=60)
    text: str = Field(min_length=1, max_length=1000)


class ChatTarget(BaseModel):
    tenant_id: UUID
    phone: str = Field(min_length=6, max_length=20)


class ResetRequest(ChatTarget):
    include_bookings: bool = False


@router.get("")
async def page() -> FileResponse:
    return FileResponse(STATIC_PAGE, media_type="text/html")


@router.get("/api/tenants", response_model=list[TenantSummary])
async def tenants(service: ServiceDep) -> list[TenantSummary]:
    return await service.tenants()


@router.get("/api/conversation", response_model=SimulatorSnapshot)
async def conversation(tenant_id: UUID, phone: str, service: ServiceDep) -> SimulatorSnapshot:
    return await service.snapshot(tenant_id, phone)


@router.post("/api/messages", response_model=SimulatorTurn)
async def send_message(body: SendRequest, service: ServiceDep) -> SimulatorTurn:
    return await service.send(body.tenant_id, body.phone, body.name, body.text)


@router.post("/api/resume-ai", response_model=SimulatorSnapshot)
async def resume_ai(body: ChatTarget, service: ServiceDep) -> SimulatorSnapshot:
    return await service.resume_ai(body.tenant_id, body.phone)


@router.post("/api/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset(body: ResetRequest, service: ServiceDep) -> None:
    await service.reset(body.tenant_id, body.phone, body.include_bookings)


class TenantTarget(BaseModel):
    tenant_id: UUID


class ConnectResponse(BaseModel):
    authorization_url: str


@router.get("/api/google", response_model=GoogleConnectionStatus)
async def google_status(tenant_id: UUID, calendar: CalendarDep) -> GoogleConnectionStatus:
    return await calendar.status(tenant_id)


@router.post("/api/google/connect", response_model=ConnectResponse)
async def google_connect(body: TenantTarget, calendar: CalendarDep) -> ConnectResponse:
    try:
        return ConnectResponse(authorization_url=calendar.dev_authorization_url(body.tenant_id))
    except GoogleNotConfiguredError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Imposta GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET ed ENCRYPTION_KEY in backend/.env",
        ) from exc
    except OAuthFlowError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


@router.post("/api/google/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def google_disconnect(body: TenantTarget, calendar: CalendarDep) -> None:
    await calendar.disconnect(body.tenant_id)
