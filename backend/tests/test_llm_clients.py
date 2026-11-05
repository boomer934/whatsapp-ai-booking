import asyncio
import json
from typing import Any

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.services.llm.base import LLMError, parse_json_object
from backend.app.services.llm.factory import FallbackLLMClient, build_llm_client
from backend.app.services.llm.gemini_client import GeminiClient
from backend.app.services.llm.groq_client import GroqClient
from backend.tests.fakes import ScriptedLLM


def mock_http(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_parse_json_object_handles_code_fences() -> None:
    assert parse_json_object('```json\n{"intent": "confirm"}\n```') == {"intent": "confirm"}
    with pytest.raises(LLMError):
        parse_json_object("non è json")
    with pytest.raises(LLMError):
        parse_json_object("[1, 2]")


def test_groq_request_and_response() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        content = json.dumps({"intent": "greeting", "answer": "Ciao!"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    async def run() -> dict[str, Any]:
        async with mock_http(handler) as http:
            return await GroqClient("KEY", "llama", http_client=http).complete_json("SYS", "USR")

    assert asyncio.run(run()) == {"intent": "greeting", "answer": "Ciao!"}
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["auth"] == "Bearer KEY"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["messages"][0] == {"role": "system", "content": "SYS"}


def test_gemini_request_and_response() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers["x-goog-api-key"]
        captured["body"] = json.loads(request.content)
        parts = [{"text": '{"intent": '}, {"text": '"confirm"}'}]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": parts}}]})

    async def run() -> dict[str, Any]:
        async with mock_http(handler) as http:
            return await GeminiClient("KEY", "gemini-2.5-flash", http_client=http).complete_json(
                "SYS", "USR"
            )

    assert asyncio.run(run()) == {"intent": "confirm"}
    assert captured["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert captured["key"] == "KEY"
    assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert captured["body"]["systemInstruction"]["parts"][0]["text"] == "SYS"


def test_http_error_becomes_llm_error() -> None:
    async def run() -> None:
        async with mock_http(lambda r: httpx.Response(429, text="rate limit")) as http:
            await GroqClient("KEY", "llama", http_client=http).complete_json("S", "U")

    with pytest.raises(LLMError, match="429"):
        asyncio.run(run())


def test_missing_key_raises() -> None:
    with pytest.raises(LLMError):
        asyncio.run(GroqClient("", "llama").complete_json("S", "U"))


def test_fallback_uses_second_provider() -> None:
    first = ScriptedLLM(LLMError("giù"))
    second = ScriptedLLM({"intent": "confirm"})
    client = FallbackLLMClient([first, second])
    assert asyncio.run(client.complete_json("S", "U")) == {"intent": "confirm"}


def test_fallback_raises_last_error_when_all_fail() -> None:
    client = FallbackLLMClient([ScriptedLLM(LLMError("a")), ScriptedLLM(LLMError("b"))])
    with pytest.raises(LLMError, match="b"):
        asyncio.run(client.complete_json("S", "U"))


def test_factory_adds_secondary_only_with_key() -> None:
    only_groq = build_llm_client(Settings(groq_api_key="g", _env_file=None))  # type: ignore[call-arg, arg-type]
    both = build_llm_client(
        Settings(llm_provider="gemini", groq_api_key="g", gemini_api_key="k", _env_file=None)  # type: ignore[call-arg, arg-type]
    )
    assert [c.name for c in only_groq._clients] == ["groq"]  # type: ignore[attr-defined]
    assert [c.name for c in both._clients] == ["gemini", "groq"]  # type: ignore[attr-defined]
