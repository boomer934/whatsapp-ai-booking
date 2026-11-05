"""Endpoint di health check (usato da Render e per svegliare l'istanza)."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=get_settings().environment)
