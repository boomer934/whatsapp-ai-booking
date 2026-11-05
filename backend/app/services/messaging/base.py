"""Interfaccia comune per l'invio di messaggi WhatsApp."""

from abc import ABC, abstractmethod

from backend.app.models.schemas import Tenant


class MessagingError(RuntimeError):
    """Errore durante l'invio di un messaggio al provider."""


class MessagingClient(ABC):
    @abstractmethod
    async def send_text(self, tenant: Tenant, to_phone: str, body: str) -> str | None:
        """Invia un messaggio di testo e restituisce l'ID assegnato dal provider."""


def to_e164(raw: str) -> str:
    """Normalizza un numero in E.164 (`+<cifre>`), rimuovendo prefissi come `whatsapp:`."""
    digits = "".join(ch for ch in raw.removeprefix("whatsapp:") if ch.isdigit())
    return f"+{digits}"
