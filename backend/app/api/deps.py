"""Dipendenze FastAPI (sovrascrivibili nei test con app.dependency_overrides)."""

from functools import lru_cache

from backend.app.core.config import get_settings
from backend.app.repositories.supabase_store import SupabaseConversationStore
from backend.app.services.calendar.availability import AvailabilityService
from backend.app.services.conversation.inbound import InboundProcessor
from backend.app.services.conversation.interpreter import MessageInterpreter
from backend.app.services.conversation.state_machine import AiReplyEngine
from backend.app.services.llm.factory import build_llm_client
from backend.app.services.messaging.factory import build_messaging_clients
from backend.app.services.notifications import WhatsAppOperatorNotifier


@lru_cache
def get_inbound_processor() -> InboundProcessor:
    settings = get_settings()
    store = SupabaseConversationStore()
    senders = build_messaging_clients(settings)
    engine = AiReplyEngine(
        store=store,
        interpreter=MessageInterpreter(build_llm_client(settings)),
        availability=AvailabilityService(store),
        notifier=WhatsAppOperatorNotifier(senders),
    )
    return InboundProcessor(store=store, engine=engine, senders=senders)
