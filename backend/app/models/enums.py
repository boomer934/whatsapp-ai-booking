"""Enum condivisi, allineati ai tipi enum definiti in supabase/migrations."""

from enum import StrEnum


class ConversationState(StrEnum):
    IDLE = "idle"
    SELECTING_SERVICE = "selecting_service"
    SELECTING_SLOT = "selecting_slot"
    CONFIRMING = "confirming"
    COMPLETED = "completed"


class ConversationMode(StrEnum):
    AI = "ai"
    MANUAL = "manual"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class BookingStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class MessagingProviderName(StrEnum):
    META = "meta"
    TWILIO = "twilio"


class MemberRole(StrEnum):
    OWNER = "owner"
    STAFF = "staff"


# Numero di fallimenti AI consecutivi dopo cui si passa all'operatore umano.
MAX_FAILED_ATTEMPTS: int = 2
