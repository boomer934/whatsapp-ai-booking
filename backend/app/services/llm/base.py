"""Interfaccia comune per i provider LLM (output JSON strutturato)."""

import json
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Errore di rete, di quota o di formato dalla API del modello."""


class LLMClient(Protocol):
    name: str

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Esegue la richiesta e restituisce l'oggetto JSON prodotto dal modello."""
        ...


def parse_json_object(raw: str) -> dict[str, Any]:
    """Interpreta il testo del modello come oggetto JSON (tollera i blocchi ```json)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Risposta del modello non è JSON valido: {raw[:200]!r}") from exc
    if not isinstance(data, dict):
        raise LLMError("La risposta del modello non è un oggetto JSON.")
    return data
