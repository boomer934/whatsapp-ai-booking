"""Client Groq (API compatibile OpenAI) con JSON mode."""

from typing import Any

import httpx

from backend.app.services.llm.base import LLMError, parse_json_object

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqClient:
    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 15.0,
        reasoning_effort: str = "",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        # Solo per modelli a ragionamento (es. gpt-oss: "low"); vuoto = non inviato.
        self._reasoning_effort = reasoning_effort
        self._http_client = http_client

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self._api_key:
            raise LLMError("GROQ_API_KEY non configurata.")
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            # Margine per i token di ragionamento dei modelli che li usano.
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        headers = {"Authorization": f"Bearer {self._api_key}"}

        client = self._http_client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(GROQ_CHAT_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"Groq non raggiungibile: {type(exc).__name__} {exc}") from exc
        finally:
            if self._http_client is None:
                await client.aclose()

        if response.is_error:
            raise LLMError(f"Groq API {response.status_code}: {response.text[:300]}")
        try:
            content: str = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("Risposta Groq in formato inatteso.") from exc
        return parse_json_object(content)
