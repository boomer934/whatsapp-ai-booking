"""Cifratura simmetrica (Fernet) per segreti salvati nel DB e stato OAuth firmato.

Fernet garantisce confidenzialità, integrità e un timestamp verificabile:
lo usiamo sia per i refresh token Google sia per il parametro `state` OAuth.
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CryptoConfigError(RuntimeError):
    """ENCRYPTION_KEY mancante o non valida."""


class InvalidEncryptedValue(ValueError):
    """Valore manomesso, cifrato con un'altra chiave o scaduto."""


class TokenCipher:
    def __init__(self, key: str) -> None:
        if not key:
            raise CryptoConfigError(
                "ENCRYPTION_KEY non configurata. Generala con: python -c "
                '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise CryptoConfigError("ENCRYPTION_KEY non è una chiave Fernet valida.") from exc

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str, ttl_seconds: int | None = None) -> str:
        try:
            return self._fernet.decrypt(token.encode(), ttl=ttl_seconds).decode()
        except InvalidToken as exc:
            raise InvalidEncryptedValue("Valore cifrato non valido o scaduto.") from exc

    def encrypt_json(self, payload: dict[str, Any]) -> str:
        return self.encrypt(json.dumps(payload, separators=(",", ":")))

    def decrypt_json(self, token: str, ttl_seconds: int | None = None) -> dict[str, Any]:
        data = json.loads(self.decrypt(token, ttl_seconds))
        if not isinstance(data, dict):
            raise InvalidEncryptedValue("Payload cifrato non valido.")
        return data
