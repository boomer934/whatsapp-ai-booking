"""Client Supabase asincrono lato server (service role, bypassa la RLS).

Ogni query del backend DEVE filtrare esplicitamente per `tenant_id`,
dato che la service role key non applica le policy RLS.
"""

import asyncio

from supabase import AsyncClient, acreate_client

from backend.app.core.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """Sollevata quando mancano le credenziali Supabase."""


_client: AsyncClient | None = None
_lock = asyncio.Lock()


async def get_supabase() -> AsyncClient:
    """Crea (una sola volta) il client Supabase con la service role key."""
    global _client
    if _client is not None:
        return _client
    async with _lock:
        if _client is None:
            settings = get_settings()
            key = settings.supabase_service_role_key.get_secret_value()
            if not settings.supabase_url or not key:
                raise DatabaseNotConfiguredError(
                    "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devono essere impostate."
                )
            _client = await acreate_client(settings.supabase_url, key)
    return _client
