"""Configurazione applicativa caricata da variabili d'ambiente / backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")

    # Messaging
    messaging_provider: Literal["meta", "twilio"] = "meta"
    meta_verify_token: SecretStr = SecretStr("")
    meta_app_secret: SecretStr = SecretStr("")
    meta_access_token: SecretStr = SecretStr("")
    meta_graph_api_version: str = "v21.0"
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")

    # LLM
    llm_provider: Literal["groq", "gemini"] = "groq"
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "llama-3.1-8b-instant"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-1.5-flash"

    # Google Calendar OAuth
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = "http://localhost:8000/oauth/google/callback"

    # Sicurezza
    encryption_key: SecretStr = SecretStr("")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Restituisce un'istanza singleton delle impostazioni."""
    return Settings()
