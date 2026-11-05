"""Router principale: aggrega tutte le rotte dell'API."""

from fastapi import APIRouter

from backend.app.api.routes import google_calendar, health, webhook_meta, webhook_twilio

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(webhook_meta.router)
api_router.include_router(webhook_twilio.router)
api_router.include_router(google_calendar.router)
