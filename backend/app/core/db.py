"""Client Supabase lato server (service role, bypassa la RLS).

Ogni query del backend DEVE filtrare esplicitamente per `tenant_id`,
dato che la service role key non applica le policy RLS.
"""

from functools import lru_cache

from supabase import Client, create_client

from backend.app.core.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """Sollevata quando mancano le credenziali Supabase."""


@lru_cache
def get_supabase() -> Client:
    """Crea (una sola volta) il client Supabase con la service role key."""
    settings = get_settings()
    key = settings.supabase_service_role_key.get_secret_value()
    if not settings.supabase_url or not key:
        raise DatabaseNotConfiguredError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devono essere impostate."
        )
    return create_client(settings.supabase_url, key)
