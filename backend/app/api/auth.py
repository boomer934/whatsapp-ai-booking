"""Autenticazione delle richieste della dashboard (token di sessione Supabase).

La dashboard invia `Authorization: Bearer <access_token Supabase>`; il token
viene verificato da Supabase Auth e l'appartenenza al tenant su tenant_members.
"""

import logging
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from supabase_auth.errors import AuthError

from backend.app.core.db import get_supabase
from backend.app.repositories.tenant_admin import SupabaseTenantAdminStore, TenantAdminStore

logger = logging.getLogger(__name__)


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str | None = None


class AuthVerifier(Protocol):
    async def verify(self, access_token: str) -> AuthenticatedUser | None:
        """None se il token non è valido o scaduto."""
        ...


class SupabaseAuthVerifier:
    async def verify(self, access_token: str) -> AuthenticatedUser | None:
        db = await get_supabase()
        try:
            response = await db.auth.get_user(access_token)
        except AuthError:
            return None
        if response is None or response.user is None:
            return None
        return AuthenticatedUser(id=UUID(response.user.id), email=response.user.email)


@lru_cache
def get_auth_verifier() -> AuthVerifier:
    return SupabaseAuthVerifier()


@lru_cache
def get_admin_store() -> TenantAdminStore:
    return SupabaseTenantAdminStore()


async def get_current_user(
    verifier: Annotated[AuthVerifier, Depends(get_auth_verifier)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token mancante",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await verifier.verify(token)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_tenant_member(
    tenant_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    admin_store: Annotated[TenantAdminStore, Depends(get_admin_store)],
) -> AuthenticatedUser:
    """Consente l'accesso solo ai membri del tenant indicato nel path."""
    if not await admin_store.is_tenant_member(tenant_id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accesso non consentito a questa attività")
    return user
