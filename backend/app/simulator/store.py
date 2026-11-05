"""Letture/scritture di supporto al simulatore (solo sviluppo)."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from backend.app.core.db import as_rows, get_supabase
from backend.app.models.enums import BookingStatus, ConversationMode, MessageDirection
from backend.app.models.schemas import Conversation


class TenantSummary(BaseModel):
    id: UUID
    name: str
    ai_enabled: bool
    operator_phone: str | None = None


class ChatMessage(BaseModel):
    direction: MessageDirection
    body: str
    created_at: datetime


class BookingSummary(BaseModel):
    id: UUID
    service_name: str | None
    starts_at: datetime
    ends_at: datetime
    status: BookingStatus
    google_event_id: str | None = None


class SimulatorStore(Protocol):
    async def list_tenants(self) -> list[TenantSummary]: ...

    async def find_conversation(self, tenant_id: UUID, phone: str) -> Conversation | None: ...

    async def list_messages(self, tenant_id: UUID, conversation_id: UUID) -> list[ChatMessage]: ...

    async def list_bookings(self, tenant_id: UUID, phone: str) -> list[BookingSummary]: ...

    async def reset(self, tenant_id: UUID, phone: str, include_bookings: bool) -> None:
        """Cancella conversazione e messaggi (e, se richiesto, le prenotazioni) del numero."""
        ...

    async def resume_ai(self, tenant_id: UUID, phone: str) -> None:
        """Riporta la chat in gestione all'AI, come farebbe l'operatore dalla dashboard."""
        ...


class SupabaseSimulatorStore:
    async def list_tenants(self) -> list[TenantSummary]:
        db = await get_supabase()
        response = (
            await db.table("tenants")
            .select("id, name, ai_enabled, operator_phone")
            .order("name")
            .execute()
        )
        return [TenantSummary.model_validate(row) for row in as_rows(response.data)]

    async def find_conversation(self, tenant_id: UUID, phone: str) -> Conversation | None:
        db = await get_supabase()
        response = (
            await db.table("conversations")
            .select("id, tenant_id, customer_phone, customer_name, state, mode, failed_attempts, context")
            .eq("tenant_id", str(tenant_id))
            .eq("customer_phone", phone)
            .limit(1)
            .execute()
        )
        rows = as_rows(response.data)
        return Conversation.model_validate(rows[0]) if rows else None

    async def list_messages(self, tenant_id: UUID, conversation_id: UUID) -> list[ChatMessage]:
        db = await get_supabase()
        response = (
            await db.table("messages")
            .select("direction, body, created_at")
            .eq("tenant_id", str(tenant_id))
            .eq("conversation_id", str(conversation_id))
            .order("created_at")
            .limit(200)
            .execute()
        )
        return [ChatMessage.model_validate(row) for row in as_rows(response.data)]

    async def list_bookings(self, tenant_id: UUID, phone: str) -> list[BookingSummary]:
        db = await get_supabase()
        bookings = as_rows(
            (
                await db.table("bookings")
                .select("id, service_id, starts_at, ends_at, status, google_event_id")
                .eq("tenant_id", str(tenant_id))
                .eq("customer_phone", phone)
                .order("starts_at")
                .execute()
            ).data
        )
        services = as_rows(
            (
                await db.table("services")
                .select("id, name")
                .eq("tenant_id", str(tenant_id))
                .execute()
            ).data
        )
        names = {row["id"]: row["name"] for row in services}
        return [
            BookingSummary.model_validate({**row, "service_name": names.get(row["service_id"])})
            for row in bookings
        ]

    async def reset(self, tenant_id: UUID, phone: str, include_bookings: bool) -> None:
        db = await get_supabase()
        if include_bookings:
            await (
                db.table("bookings")
                .delete()
                .eq("tenant_id", str(tenant_id))
                .eq("customer_phone", phone)
                .execute()
            )
        # I messaggi vengono eliminati in cascata con la conversazione.
        await (
            db.table("conversations")
            .delete()
            .eq("tenant_id", str(tenant_id))
            .eq("customer_phone", phone)
            .execute()
        )

    async def resume_ai(self, tenant_id: UUID, phone: str) -> None:
        db = await get_supabase()
        await (
            db.table("conversations")
            .update({"mode": ConversationMode.AI.value, "failed_attempts": 0})
            .eq("tenant_id", str(tenant_id))
            .eq("customer_phone", phone)
            .execute()
        )
