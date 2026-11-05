"""Implementazione di ConversationStore su Supabase.

Usa la service role key: ogni query filtra esplicitamente per tenant_id.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from postgrest.exceptions import APIError

from backend.app.core.db import as_rows, get_supabase
from backend.app.models.enums import BookingStatus, MessageDirection, MessagingProviderName
from backend.app.models.schemas import (
    BusinessHours,
    Conversation,
    InboundMessage,
    Service,
    Tenant,
)

# SQLSTATE di violazione del vincolo di esclusione bookings_no_overlap.
EXCLUSION_VIOLATION = "23P01"
_SERVICE_COLUMNS = "id, tenant_id, name, duration_minutes, price_cents, is_active"


_TENANT_COLUMNS = (
    "id, name, timezone, ai_enabled, messaging_provider, "
    "wa_phone_number_id, wa_phone_e164, operator_phone"
)
_CONVERSATION_COLUMNS = (
    "id, tenant_id, customer_phone, customer_name, state, mode, failed_attempts, context"
)
_ROUTING_COLUMN: dict[MessagingProviderName, str] = {
    MessagingProviderName.META: "wa_phone_number_id",
    MessagingProviderName.TWILIO: "wa_phone_e164",
    MessagingProviderName.SIMULATOR: "id",
}


class SupabaseConversationStore:
    async def get_tenant_by_routing_key(
        self, provider: MessagingProviderName, routing_key: str
    ) -> Tenant | None:
        db = await get_supabase()
        response = (
            await db.table("tenants")
            .select(_TENANT_COLUMNS)
            .eq(_ROUTING_COLUMN[provider], routing_key)
            .limit(1)
            .execute()
        )
        rows = as_rows(response.data)
        return Tenant.model_validate(rows[0]) if rows else None

    async def get_or_create_conversation(
        self, tenant_id: UUID, customer_phone: str, customer_name: str | None
    ) -> Conversation:
        db = await get_supabase()
        # Insert idempotente: se esiste già non modifica lo stato.
        await (
            db.table("conversations")
            .upsert(
                {
                    "tenant_id": str(tenant_id),
                    "customer_phone": customer_phone,
                    "customer_name": customer_name,
                },
                on_conflict="tenant_id,customer_phone",
                ignore_duplicates=True,
            )
            .execute()
        )
        response = (
            await db.table("conversations")
            .select(_CONVERSATION_COLUMNS)
            .eq("tenant_id", str(tenant_id))
            .eq("customer_phone", customer_phone)
            .single()
            .execute()
        )
        return Conversation.model_validate(response.data)

    async def save_inbound_message(
        self, conversation: Conversation, message: InboundMessage
    ) -> bool:
        db = await get_supabase()
        # ignore_duplicates + vincolo unique(tenant_id, provider_message_id):
        # un webhook ripetuto non restituisce righe.
        response = (
            await db.table("messages")
            .upsert(
                {
                    "tenant_id": str(conversation.tenant_id),
                    "conversation_id": str(conversation.id),
                    "direction": MessageDirection.INBOUND.value,
                    "body": message.text or "[messaggio non testuale]",
                    "provider_message_id": message.provider_message_id,
                },
                on_conflict="tenant_id,provider_message_id",
                ignore_duplicates=True,
            )
            .execute()
        )
        if not response.data:
            return False

        update: dict[str, Any] = {"last_message_at": message.received_at.isoformat()}
        if message.customer_name and not conversation.customer_name:
            update["customer_name"] = message.customer_name
        await (
            db.table("conversations")
            .update(update)
            .eq("id", str(conversation.id))
            .eq("tenant_id", str(conversation.tenant_id))
            .execute()
        )
        return True

    async def save_outbound_message(
        self, conversation: Conversation, body: str, provider_message_id: str | None
    ) -> None:
        db = await get_supabase()
        await (
            db.table("messages")
            .insert(
                {
                    "tenant_id": str(conversation.tenant_id),
                    "conversation_id": str(conversation.id),
                    "direction": MessageDirection.OUTBOUND.value,
                    "body": body,
                    "provider_message_id": provider_message_id,
                }
            )
            .execute()
        )
        await (
            db.table("conversations")
            .update({"last_message_at": datetime.now(UTC).isoformat()})
            .eq("id", str(conversation.id))
            .eq("tenant_id", str(conversation.tenant_id))
            .execute()
        )

    async def update_conversation(self, conversation: Conversation) -> None:
        db = await get_supabase()
        await (
            db.table("conversations")
            .update(
                {
                    "state": conversation.state.value,
                    "mode": conversation.mode.value,
                    "failed_attempts": conversation.failed_attempts,
                    "context": conversation.context,
                    "customer_name": conversation.customer_name,
                }
            )
            .eq("id", str(conversation.id))
            .eq("tenant_id", str(conversation.tenant_id))
            .execute()
        )

    async def list_active_services(self, tenant_id: UUID) -> list[Service]:
        db = await get_supabase()
        response = (
            await db.table("services")
            .select(_SERVICE_COLUMNS)
            .eq("tenant_id", str(tenant_id))
            .eq("is_active", True)
            .order("name")
            .order("id")
            .execute()
        )
        return [Service.model_validate(row) for row in response.data]

    async def list_business_hours(self, tenant_id: UUID) -> list[BusinessHours]:
        db = await get_supabase()
        response = (
            await db.table("business_hours")
            .select("weekday, open_time, close_time")
            .eq("tenant_id", str(tenant_id))
            .execute()
        )
        return [BusinessHours.model_validate(row) for row in response.data]

    async def list_busy_intervals(
        self, tenant_id: UUID, start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        db = await get_supabase()
        response = (
            await db.table("bookings")
            .select("starts_at, ends_at")
            .eq("tenant_id", str(tenant_id))
            .eq("status", BookingStatus.CONFIRMED.value)
            .lt("starts_at", end.isoformat())
            .gt("ends_at", start.isoformat())
            .execute()
        )
        return [
            (datetime.fromisoformat(row["starts_at"]), datetime.fromisoformat(row["ends_at"]))
            for row in as_rows(response.data)
        ]

    async def create_booking(
        self,
        conversation: Conversation,
        service: Service,
        starts_at: datetime,
        ends_at: datetime,
    ) -> UUID | None:
        db = await get_supabase()
        try:
            response = (
                await db.table("bookings")
                .insert(
                    {
                        "tenant_id": str(conversation.tenant_id),
                        "conversation_id": str(conversation.id),
                        "service_id": str(service.id),
                        "customer_phone": conversation.customer_phone,
                        "customer_name": conversation.customer_name,
                        "starts_at": starts_at.isoformat(),
                        "ends_at": ends_at.isoformat(),
                    }
                )
                .execute()
            )
        except APIError as exc:
            if exc.code == EXCLUSION_VIOLATION:
                return None
            raise
        return UUID(str(as_rows(response.data)[0]["id"]))

    async def set_booking_google_event(
        self, tenant_id: UUID, booking_id: UUID, google_event_id: str
    ) -> None:
        db = await get_supabase()
        await (
            db.table("bookings")
            .update({"google_event_id": google_event_id})
            .eq("id", str(booking_id))
            .eq("tenant_id", str(tenant_id))
            .execute()
        )
