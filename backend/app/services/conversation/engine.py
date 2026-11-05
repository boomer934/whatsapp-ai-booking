"""Motore di risposta: decide cosa rispondere a un messaggio del cliente.

Lo step 4 usa una risposta segnaposto; negli step 5-6 verrà sostituito dal
motore AI con state machine e handover.
"""

from typing import Protocol

from backend.app.models.schemas import Conversation, InboundMessage, Tenant


class ReplyEngine(Protocol):
    async def reply(
        self, tenant: Tenant, conversation: Conversation, message: InboundMessage
    ) -> str | None:
        """Restituisce il testo da inviare, oppure None per non rispondere."""
        ...


class PlaceholderReplyEngine:
    """Conferma la ricezione: serve a verificare il giro completo dei webhook."""

    async def reply(
        self, tenant: Tenant, conversation: Conversation, message: InboundMessage
    ) -> str | None:
        if message.text is None:
            return "Per ora riesco a leggere solo messaggi di testo. Puoi scrivermi?"
        return f"Ciao! Sono l'assistente di {tenant.name}. Ti rispondiamo a breve."
