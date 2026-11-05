"""Costruzione del client LLM con fallback automatico tra provider."""

import logging
from typing import Any

from backend.app.core.config import Settings
from backend.app.services.llm.base import LLMClient, LLMError
from backend.app.services.llm.gemini_client import GeminiClient
from backend.app.services.llm.groq_client import GroqClient

logger = logging.getLogger(__name__)


class FallbackLLMClient:
    """Prova i provider in ordine e passa al successivo in caso di errore."""

    name = "fallback"

    def __init__(self, clients: list[LLMClient]) -> None:
        if not clients:
            raise ValueError("Serve almeno un client LLM.")
        self._clients = clients

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        last_error: LLMError | None = None
        for client in self._clients:
            try:
                return await client.complete_json(system_prompt, user_prompt)
            except LLMError as exc:
                logger.warning("LLM %s fallito: %s", client.name, exc)
                last_error = exc
        assert last_error is not None
        raise last_error


def build_llm_client(settings: Settings) -> LLMClient:
    groq = GroqClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort=settings.groq_reasoning_effort,
    )
    gemini = GeminiClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout=settings.llm_timeout_seconds,
        thinking_level=settings.gemini_thinking_level,
    )
    primary: GroqClient | GeminiClient
    secondary: GroqClient | GeminiClient
    primary, secondary = (groq, gemini) if settings.llm_provider == "groq" else (gemini, groq)
    if not primary.is_configured:
        logger.warning("Chiave API del provider LLM primario (%s) mancante.", primary.name)
    clients: list[LLMClient] = [primary]
    if secondary.is_configured:
        clients.append(secondary)
    return FallbackLLMClient(clients)
