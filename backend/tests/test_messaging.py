import asyncio
import json

import httpx

from backend.app.core.security import (
    compute_twilio_signature,
    verify_meta_signature,
    verify_twilio_signature,
)
from backend.app.models.enums import MessagingProviderName
from backend.app.services.messaging.base import to_e164
from backend.app.services.messaging.meta_whatsapp import MetaWhatsAppClient, parse_meta_payload
from backend.app.services.messaging.twilio_whatsapp import (
    TwilioWhatsAppClient,
    parse_twilio_form,
)
from backend.tests.fakes import make_tenant

META_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WABA",
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "390000", "phone_number_id": "PNID-1"},
                        "contacts": [{"wa_id": "393331112222", "profile": {"name": "Mario"}}],
                        "messages": [
                            {
                                "from": "393331112222",
                                "id": "wamid.ABC",
                                "timestamp": "1762300000",
                                "type": "text",
                                "text": {"body": "vorrei venire domani verso le 15"},
                            },
                            {
                                "from": "393331112222",
                                "id": "wamid.IMG",
                                "timestamp": "1762300001",
                                "type": "image",
                                "image": {"id": "media"},
                            },
                        ],
                    },
                }
            ],
        }
    ],
}

META_STATUS_PAYLOAD = {
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "metadata": {"phone_number_id": "PNID-1"},
                        "statuses": [{"id": "wamid.X", "status": "delivered"}],
                    }
                }
            ]
        }
    ]
}


def test_to_e164() -> None:
    assert to_e164("whatsapp:+39 333 111 2222") == "+393331112222"
    assert to_e164("393331112222") == "+393331112222"


def test_parse_meta_text_and_media() -> None:
    messages = parse_meta_payload(META_PAYLOAD)
    assert len(messages) == 2
    text_msg, image_msg = messages
    assert text_msg.provider == MessagingProviderName.META
    assert text_msg.routing_key == "PNID-1"
    assert text_msg.customer_phone == "+393331112222"
    assert text_msg.customer_name == "Mario"
    assert text_msg.text == "vorrei venire domani verso le 15"
    assert image_msg.text is None


def test_parse_meta_ignores_status_updates() -> None:
    assert parse_meta_payload(META_STATUS_PAYLOAD) == []


def test_parse_twilio_form() -> None:
    message = parse_twilio_form(
        {
            "MessageSid": "SM123",
            "From": "whatsapp:+393331112222",
            "To": "whatsapp:+14155238886",
            "Body": " Ciao ",
            "ProfileName": "Mario",
            "NumMedia": "0",
        }
    )
    assert message is not None
    assert message.routing_key == "+14155238886"
    assert message.customer_phone == "+393331112222"
    assert message.text == "Ciao"


def test_parse_twilio_form_missing_fields() -> None:
    assert parse_twilio_form({"Body": "x"}) is None


def test_meta_signature() -> None:
    import hashlib
    import hmac

    body = b'{"a":1}'
    good = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, good, "secret")
    assert not verify_meta_signature(body, good, "altro")
    assert not verify_meta_signature(body, None, "secret")
    assert not verify_meta_signature(b'{"a":2}', good, "secret")


def test_twilio_signature_matches_official_example() -> None:
    # Esempio dalla documentazione Twilio "Webhooks security".
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = {
        "CallSid": "CA1234567890ABCDE",
        "Caller": "+12349013030",
        "Digits": "1234",
        "From": "+12349013030",
        "To": "+18005551212",
    }
    expected = "0/KCTR6DLpKmkAf8muzZqo1nDgQ="
    assert compute_twilio_signature(url, params, "12345") == expected
    assert verify_twilio_signature(url, params, expected, "12345")
    assert not verify_twilio_signature(url, params, expected, "sbagliato")


def test_meta_client_sends_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.OUT"}]})

    async def run() -> str | None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = MetaWhatsAppClient("TOKEN", "v21.0", http_client=http)
            return await client.send_text(make_tenant(), "+393331112222", "Ciao")

    assert asyncio.run(run()) == "wamid.OUT"
    assert captured["url"] == "https://graph.facebook.com/v21.0/PNID-1/messages"
    assert captured["auth"] == "Bearer TOKEN"
    assert captured["json"] == {
        "messaging_product": "whatsapp",
        "to": "393331112222",
        "type": "text",
        "text": {"body": "Ciao", "preview_url": False},
    }


def test_twilio_client_sends_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["form"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(201, json={"sid": "SMOUT"})

    async def run() -> str | None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = TwilioWhatsAppClient("AC1", "tok", http_client=http)
            return await client.send_text(make_tenant(), "+393331112222", "Ciao")

    assert asyncio.run(run()) == "SMOUT"
    assert captured["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages.json"
    assert captured["form"] == {
        "From": "whatsapp:+14155238886",
        "To": "whatsapp:+393331112222",
        "Body": "Ciao",
    }
