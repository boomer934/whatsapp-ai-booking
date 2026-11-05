"""Dipendenze FastAPI (sovrascrivibili nei test con app.dependency_overrides)."""

from functools import lru_cache

from backend.app.core.config import get_settings
from backend.app.repositories.supabase_store import SupabaseConversationStore
from backend.app.services.conversation.engine import PlaceholderReplyEngine
from backend.app.services.conversation.inbound import InboundProcessor
from backend.app.services.messaging.factory import build_messaging_clients


@lru_cache
def get_inbound_processor() -> InboundProcessor:
    return InboundProcessor(
        store=SupabaseConversationStore(),
        engine=PlaceholderReplyEngine(),
        senders=build_messaging_clients(get_settings()),
    )
