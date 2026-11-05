"""Interfaccia del motore di risposta (implementazione: state_machine.AiReplyEngine)."""

from typing import Protocol

from backend.app.models.schemas import Conversation, InboundMessage, Tenant


class ReplyEngine(Protocol):
    async def reply(
        self, tenant: Tenant, conversation: Conversation, message: InboundMessage
    ) -> str | None:
        """Restituisce il testo da inviare, oppure None per non rispondere."""
        ...
