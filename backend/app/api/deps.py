"""Composizione delle dipendenze (sovrascrivibili nei test con app.dependency_overrides)."""

from functools import lru_cache

from backend.app.api.auth import get_admin_store
from backend.app.core.config import get_settings
from backend.app.repositories.supabase_store import SupabaseConversationStore
from backend.app.services.calendar.availability import AvailabilityService, CombinedBusyProvider
from backend.app.services.calendar.google_calendar import GoogleCalendarService
from backend.app.services.calendar.google_client import GoogleCalendarClient
from backend.app.services.conversation.inbound import InboundProcessor
from backend.app.services.conversation.interpreter import MessageInterpreter
from backend.app.services.conversation.state_machine import AiReplyEngine
from backend.app.services.llm.factory import build_llm_client
from backend.app.services.messaging.factory import build_messaging_clients
from backend.app.services.notifications import WhatsAppOperatorNotifier


@lru_cache
def get_conversation_store() -> SupabaseConversationStore:
    return SupabaseConversationStore()


@lru_cache
def get_google_calendar_service() -> GoogleCalendarService:
    settings = get_settings()
    return GoogleCalendarService(
        client=GoogleCalendarClient(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
            redirect_uri=settings.google_redirect_uri,
        ),
        admin_store=get_admin_store(),
        booking_store=get_conversation_store(),
        encryption_key=settings.encryption_key.get_secret_value(),
    )


@lru_cache
def get_inbound_processor() -> InboundProcessor:
    settings = get_settings()
    store = get_conversation_store()
    calendar = get_google_calendar_service()
    senders = build_messaging_clients(settings)
    engine = AiReplyEngine(
        store=store,
        interpreter=MessageInterpreter(build_llm_client(settings)),
        availability=AvailabilityService(CombinedBusyProvider(store, calendar)),
        notifier=WhatsAppOperatorNotifier(senders),
        booking_sync=calendar,
    )
    return InboundProcessor(store=store, engine=engine, senders=senders)
