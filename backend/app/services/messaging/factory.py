"""Costruzione dei client di messaggistica a partire dalle impostazioni."""

from backend.app.core.config import Settings
from backend.app.models.enums import MessagingProviderName
from backend.app.services.messaging.base import MessagingClient
from backend.app.services.messaging.meta_whatsapp import MetaWhatsAppClient
from backend.app.services.messaging.twilio_whatsapp import TwilioWhatsAppClient


def build_messaging_clients(settings: Settings) -> dict[MessagingProviderName, MessagingClient]:
    return {
        MessagingProviderName.META: MetaWhatsAppClient(
            access_token=settings.meta_access_token.get_secret_value(),
            api_version=settings.meta_graph_api_version,
        ),
        MessagingProviderName.TWILIO: TwilioWhatsAppClient(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token.get_secret_value(),
        ),
    }
