"""Controlli sulla configurazione di produzione (avvio fail-fast)."""

import pytest

from backend.app.core.config import Settings, get_settings
from backend.main import create_app
from backend.tests.fakes import PRODUCTION_ENV


def _settings(**overrides: str) -> Settings:
    values = {k.lower(): v for k, v in PRODUCTION_ENV.items()} | overrides
    return Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


def test_valid_production_config_has_no_problems() -> None:
    assert _settings().production_problems() == []


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"frontend_url": "http://localhost:3000"}, "FRONTEND_URL"),
        ({"public_base_url": ""}, "PUBLIC_BASE_URL"),
        ({"supabase_service_role_key": ""}, "SUPABASE_SERVICE_ROLE_KEY"),
        ({"groq_api_key": ""}, "chiave LLM"),
        ({"encryption_key": "non-valida"}, "ENCRYPTION_KEY"),
        ({"google_redirect_uri": "http://localhost:8000/oauth/google/callback"}, "GOOGLE_REDIRECT_URI"),
    ],
)
def test_production_problems_are_detected(override: dict[str, str], expected: str) -> None:
    problems = _settings(**override).production_problems()
    assert any(expected in p for p in problems), problems


def test_gemini_alone_is_enough() -> None:
    assert _settings(groq_api_key="", gemini_api_key="k").production_problems() == []


def test_secrets_never_appear_in_messages() -> None:
    problems = _settings(public_base_url="", encryption_key="segreto-sbagliato").production_problems()
    assert problems and not any("segreto-sbagliato" in p for p in problems)


def test_app_refuses_to_start_with_bad_production_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="FRONTEND_URL"):
            create_app()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_api_schema_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    for key, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/health").status_code == 200
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
