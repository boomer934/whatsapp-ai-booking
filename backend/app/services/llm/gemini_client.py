"""Client Google Gemini (REST generateContent) con output JSON."""

from typing import Any

import httpx

from backend.app.services.llm.base import LLMError, parse_json_object

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 15.0,
        thinking_level: str = "",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        # Modelli Gemini 3: "minimal"/"low" riducono molto la latenza; vuoto = default.
        self._thinking_level = thinking_level
        self._http_client = http_client

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self._api_key:
            raise LLMError("GEMINI_API_KEY non configurata.")
        url = f"{GEMINI_BASE_URL}/{self._model}:generateContent"
        generation_config: dict[str, Any] = {
            "temperature": 0.1,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        }
        if self._thinking_level:
            generation_config["thinkingConfig"] = {"thinkingLevel": self._thinking_level}
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }
        headers = {"x-goog-api-key": self._api_key}

        client = self._http_client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini non raggiungibile: {type(exc).__name__} {exc}") from exc
        finally:
            if self._http_client is None:
                await client.aclose()

        if response.is_error:
            raise LLMError(f"Gemini API {response.status_code}: {response.text[:300]}")
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("Risposta Gemini in formato inatteso.") from exc
        return parse_json_object(content)
