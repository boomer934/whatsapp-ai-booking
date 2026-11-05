"""Gestione prenotazioni dalla dashboard (operazioni che toccano anche Google Calendar)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.app.api.auth import AuthenticatedUser, get_admin_store, require_tenant_member
from backend.app.api.deps import get_google_calendar_service
from backend.app.models.enums import BookingStatus
from backend.app.repositories.tenant_admin import TenantAdminStore
from backend.app.services.calendar.google_calendar import GoogleCalendarService

router = APIRouter(tags=["bookings"])

MemberDep = Annotated[AuthenticatedUser, Depends(require_tenant_member)]
AdminDep = Annotated[TenantAdminStore, Depends(get_admin_store)]
CalendarDep = Annotated[GoogleCalendarService, Depends(get_google_calendar_service)]


class CancelResponse(BaseModel):
    status: BookingStatus
    google_event_removed: bool


@router.post(
    "/api/tenants/{tenant_id}/bookings/{booking_id}/cancel", response_model=CancelResponse
)
async def cancel_booking(
    tenant_id: UUID,
    booking_id: UUID,
    _user: MemberDep,
    admin: AdminDep,
    calendar: CalendarDep,
) -> CancelResponse:
    """Annulla la prenotazione (lo slot torna libero) e rimuove l'evento Google."""
    booking = await admin.get_booking(tenant_id, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prenotazione non trovata")
    if booking.status != BookingStatus.CANCELLED:
        await admin.cancel_booking(tenant_id, booking_id)
    removed = (
        await calendar.on_booking_cancelled(tenant_id, booking.google_event_id)
        if booking.google_event_id
        else False
    )
    return CancelResponse(status=BookingStatus.CANCELLED, google_event_removed=removed)
