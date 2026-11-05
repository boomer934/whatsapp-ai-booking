"""Persistenza per le funzioni di amministrazione del tenant (dashboard).

Membership utente/tenant e credenziali Google Calendar.
"""

from typing import Protocol
from uuid import UUID

from postgrest.types import CountMethod

from backend.app.core.db import as_rows, get_supabase
from backend.app.models.schemas import GoogleCredentials


class TenantAdminStore(Protocol):
    async def is_tenant_member(self, tenant_id: UUID, user_id: UUID) -> bool: ...

    async def get_google_credentials(self, tenant_id: UUID) -> GoogleCredentials | None: ...

    async def save_google_credentials(self, credentials: GoogleCredentials) -> None:
        """Crea o sostituisce il collegamento del tenant."""
        ...

    async def delete_google_credentials(self, tenant_id: UUID) -> None: ...


class SupabaseTenantAdminStore:
    async def is_tenant_member(self, tenant_id: UUID, user_id: UUID) -> bool:
        db = await get_supabase()
        response = (
            await db.table("tenant_members")
            .select("id", count=CountMethod.exact)
            .eq("tenant_id", str(tenant_id))
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
        return bool(response.count)

    async def get_google_credentials(self, tenant_id: UUID) -> GoogleCredentials | None:
        db = await get_supabase()
        response = (
            await db.table("google_credentials")
            .select("tenant_id, google_account_email, refresh_token_encrypted, calendar_id")
            .eq("tenant_id", str(tenant_id))
            .limit(1)
            .execute()
        )
        rows = as_rows(response.data)
        return GoogleCredentials.model_validate(rows[0]) if rows else None

    async def save_google_credentials(self, credentials: GoogleCredentials) -> None:
        db = await get_supabase()
        await (
            db.table("google_credentials")
            .upsert(credentials.model_dump(mode="json"), on_conflict="tenant_id")
            .execute()
        )

    async def delete_google_credentials(self, tenant_id: UUID) -> None:
        db = await get_supabase()
        await db.table("google_credentials").delete().eq("tenant_id", str(tenant_id)).execute()
