"""Dati della prenotazione in corso, salvati in conversations.context (jsonb)."""

import logging
from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from backend.app.models.schemas import Conversation
from backend.app.services.calendar.availability import PartOfDay

logger = logging.getLogger(__name__)


class BookingContext(BaseModel):
    service_id: UUID | None = None
    # Preferenze espresse prima di aver scelto il servizio.
    day: date | None = None
    at: time | None = None
    part_of_day: PartOfDay | None = None
    # Slot proposti al cliente (scelta per numero) e slot da confermare.
    proposed_slots: list[datetime] = []
    selected_slot: datetime | None = None

    @classmethod
    def from_conversation(cls, conversation: Conversation) -> "BookingContext":
        try:
            return cls.model_validate(conversation.context)
        except ValidationError:
            logger.warning("Context non valido per la conversazione %s: azzerato", conversation.id)
            return cls()

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
