"""Configurazione applicativa caricata da variabili d'ambiente / backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Tutte le impostazioni dell'app. I segreti sono opzionali per permettere
    l'avvio in locale; i servizi che li richiedono falliscono in modo esplicito."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Generale
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:3000"

    # Supabase (URL base del progetto; chiave service_role o "sb_secret_...")
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")

    @field_validator("supabase_url")
    @classmethod
    def _normalize_supabase_url(cls, value: str) -> str:
        """Accetta anche l'URL REST copiato dalla dashboard (…/rest/v1/)."""
        value = value.strip().rstrip("/")
        return value.removesuffix("/rest/v1")

    # URL pubblico del backend (es. https://xxx.onrender.com). Serve a ricostruire
    # l'URL esatto firmato da Twilio quando l'app gira dietro un proxy.
    public_base_url: str = ""

    # Messaging (il provider usato è quello del webhook in arrivo)
    meta_verify_token: SecretStr = SecretStr("")
    meta_app_secret: SecretStr = SecretStr("")
    meta_access_token: SecretStr = SecretStr("")
    meta_graph_api_version: str = "v21.0"
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")

    # LLM (il provider non primario, se ha una chiave, fa da fallback)
    llm_provider: Literal["groq", "gemini"] = "groq"
    llm_timeout_seconds: float = 15.0
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-20b"
    groq_reasoning_effort: str = "low"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_thinking_level: str = "minimal"

    # Google Calendar OAuth
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = "http://localhost:8000/oauth/google/callback"

    # Simulatore WhatsApp locale (/simulator): mai attivo in production.
    simulator_enabled: bool = True

    # Sicurezza
    encryption_key: SecretStr = SecretStr("")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def simulator_active(self) -> bool:
        return self.simulator_enabled and not self.is_production


@lru_cache
def get_settings() -> Settings:
    """Restituisce un'istanza singleton delle impostazioni."""
    return Settings()
