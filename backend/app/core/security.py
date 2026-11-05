"""Verifica delle firme dei webhook in arrivo (Meta e Twilio)."""

import base64
import hashlib
import hmac
from collections.abc import Mapping


def verify_meta_signature(body: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Verifica l'header `X-Hub-Signature-256: sha256=<hex>` inviato da Meta.

    La firma è l'HMAC-SHA256 del body grezzo con l'App Secret.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header.removeprefix("sha256="), expected)


def compute_twilio_signature(url: str, params: Mapping[str, str], auth_token: str) -> str:
    """Firma Twilio: HMAC-SHA1 (base64) di URL + parametri POST ordinati per chiave."""
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def verify_twilio_signature(
    url: str,
    params: Mapping[str, str],
    signature_header: str | None,
    auth_token: str,
) -> bool:
    """Verifica l'header `X-Twilio-Signature`."""
    if not signature_header:
        return False
    expected = compute_twilio_signature(url, params, auth_token)
    return hmac.compare_digest(signature_header, expected)
