import hashlib
import hmac
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app.api.deps import get_inbound_processor
from backend.app.core.config import Settings, get_settings
from backend.app.core.security import compute_twilio_signature
from backend.app.models.schemas import InboundMessage
from backend.main import app
from backend.tests.test_messaging import META_PAYLOAD

META_SECRET = "meta-app-secret"
TWILIO_TOKEN = "twilio-token"
PUBLIC_URL = "https://api.esempio.it"


class RecordingProcessor:
    def __init__(self) -> None:
        self.received: list[InboundMessage] = []

    async def process_safely(self, message: InboundMessage) -> None:
        self.received.append(message)


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "test",
        "public_base_url": PUBLIC_URL,
        "meta_verify_token": SecretStr("verify-me"),
        "meta_app_secret": SecretStr(META_SECRET),
        "twilio_auth_token": SecretStr(TWILIO_TOKEN),
    }
    base.update(overrides)
    return Settings.model_validate(base)


@pytest.fixture
def processor() -> Iterator[RecordingProcessor]:
    recorder = RecordingProcessor()
    app.dependency_overrides[get_inbound_processor] = lambda: recorder
    app.dependency_overrides[get_settings] = lambda: make_settings()
    yield recorder
    app.dependency_overrides.clear()


@pytest.fixture
def client(processor: RecordingProcessor) -> TestClient:
    return TestClient(app)


# --- Meta -------------------------------------------------------------------


def test_meta_verification_ok(client: TestClient) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"}
    response = client.get("/webhooks/meta", params=params)
    assert response.status_code == 200
    assert response.text == "42"


def test_meta_verification_wrong_token(client: TestClient) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"}
    assert client.get("/webhooks/meta", params=params).status_code == 403


def test_meta_post_valid_signature(client: TestClient, processor: RecordingProcessor) -> None:
    body = json.dumps(META_PAYLOAD).encode()
    signature = "sha256=" + hmac.new(META_SECRET.encode(), body, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhooks/meta",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [m.provider_message_id for m in processor.received] == ["wamid.ABC", "wamid.IMG"]


def test_meta_post_invalid_signature(client: TestClient, processor: RecordingProcessor) -> None:
    response = client.post(
        "/webhooks/meta",
        content=json.dumps(META_PAYLOAD).encode(),
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert response.status_code == 403
    assert processor.received == []


def test_meta_post_without_secret_rejected_in_production(
    client: TestClient, processor: RecordingProcessor
) -> None:
    app.dependency_overrides[get_settings] = lambda: make_settings(
        environment="production", meta_app_secret=SecretStr("")
    )
    response = client.post("/webhooks/meta", content=json.dumps(META_PAYLOAD).encode())
    assert response.status_code == 403
    assert processor.received == []


# --- Twilio -----------------------------------------------------------------

TWILIO_FORM = {
    "MessageSid": "SM123",
    "From": "whatsapp:+393331112222",
    "To": "whatsapp:+14155238886",
    "Body": "Ciao",
    "ProfileName": "Mario",
    "NumMedia": "0",
}


def test_twilio_post_valid_signature(client: TestClient, processor: RecordingProcessor) -> None:
    signature = compute_twilio_signature(f"{PUBLIC_URL}/webhooks/twilio", TWILIO_FORM, TWILIO_TOKEN)
    response = client.post(
        "/webhooks/twilio", data=TWILIO_FORM, headers={"X-Twilio-Signature": signature}
    )
    assert response.status_code == 200
    assert "<Response>" in response.text
    assert len(processor.received) == 1
    assert processor.received[0].routing_key == "+14155238886"


def test_twilio_post_invalid_signature(client: TestClient, processor: RecordingProcessor) -> None:
    response = client.post(
        "/webhooks/twilio", data=TWILIO_FORM, headers={"X-Twilio-Signature": "falsa"}
    )
    assert response.status_code == 403
    assert processor.received == []
