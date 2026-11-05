"""Test del simulatore WhatsApp (pipeline reale con store e LLM finti)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.app.api.deps import get_simulator_service
from backend.app.core.config import get_settings
from backend.app.models.enums import ConversationMode, MessageDirection
from backend.app.models.schemas import Conversation
from backend.app.services.calendar.availability import AvailabilityService
from backend.app.services.conversation.interpreter import MessageInterpreter
from backend.app.simulator.service import SimulatorService
from backend.app.simulator.store import BookingSummary, ChatMessage, TenantSummary
from backend.main import app, create_app
from backend.tests.fakes import PRODUCTION_ENV, FakeBookingStore, ScriptedLLM, make_service, make_tenant

PHONE = "+390000000001"


class FakeSimulatorStore:
    def __init__(self, store: FakeBookingStore) -> None:
        self.store = store

    async def list_tenants(self) -> list[TenantSummary]:
        return [
            TenantSummary(id=t.id, name=t.name, ai_enabled=t.ai_enabled, operator_phone=t.operator_phone)
            for t in self.store.tenants
        ]

    async def find_conversation(self, tenant_id: UUID, phone: str) -> Conversation | None:
        return self.store.conversations.get((tenant_id, phone))

    async def list_messages(self, tenant_id: UUID, conversation_id: UUID) -> list[ChatMessage]:
        return [
            ChatMessage(direction=MessageDirection(d), body=b, created_at=datetime.now(UTC))
            for cid, d, b in self.store.log
            if cid == conversation_id
        ]

    async def list_bookings(self, tenant_id: UUID, phone: str) -> list[BookingSummary]:
        return []

    async def reset(self, tenant_id: UUID, phone: str, include_bookings: bool) -> None:
        conversation = self.store.conversations.pop((tenant_id, phone), None)
        if conversation:
            self.store.log = [e for e in self.store.log if e[0] != conversation.id]
        if include_bookings:
            self.store.bookings.clear()

    async def resume_ai(self, tenant_id: UUID, phone: str) -> None:
        conversation = self.store.conversations[(tenant_id, phone)]
        conversation.mode, conversation.failed_attempts = ConversationMode.AI, 0


class Env:
    def __init__(self, *llm: dict[str, Any]) -> None:
        self.tenant = make_tenant(name="Salone Demo", operator_phone="+390000000999")
        services = [make_service(self.tenant.id, "Taglio uomo", 30, 2000)]
        self.store = FakeBookingStore([self.tenant], services)
        self.llm = ScriptedLLM(*llm)
        self.service = SimulatorService(
            store=self.store,
            sim_store=FakeSimulatorStore(self.store),
            interpreter=MessageInterpreter(self.llm),
            availability=AvailabilityService(self.store),
        )
        self.client = TestClient(app)

    def send(self, text: str, **extra: Any) -> Any:
        body = {"tenant_id": str(self.tenant.id), "phone": PHONE, "name": "Mario", "text": text}
        return self.client.post("/simulator/api/messages", json=body, **extra)


@pytest.fixture
def make_env() -> Iterator[Any]:
    def factory(*llm: dict[str, Any]) -> Env:
        env = Env(*llm)
        app.dependency_overrides[get_simulator_service] = lambda: env.service
        return env

    yield factory
    app.dependency_overrides.clear()


def test_page_and_tenants(make_env: Any) -> None:
    env = make_env()
    page = env.client.get("/simulator")
    assert page.status_code == 200 and "Simulatore WhatsApp" in page.text
    assert env.client.get("/simulator/api/tenants").json()[0]["name"] == "Salone Demo"


def test_requests_through_tunnel_or_proxy_are_rejected(make_env: Any) -> None:
    env = make_env({"intent": "greeting", "answer": "Ciao!"})
    for header in ("X-Forwarded-For", "Cf-Connecting-Ip"):
        assert env.client.get("/simulator", headers={header: "1.2.3.4"}).status_code == 403
        assert env.send("ciao", headers={header: "1.2.3.4"}).status_code == 403
    assert env.llm.prompts == []


def test_message_runs_real_pipeline_and_returns_reply(make_env: Any) -> None:
    env = make_env({"intent": "greeting", "answer": "Ciao! Vuoi prenotare?"})
    turn = env.send("buongiorno").json()

    assert turn["replies"] == ["Ciao! Vuoi prenotare?"]
    assert turn["operator_notifications"] == [] and turn["error"] is None
    snapshot = turn["snapshot"]
    assert snapshot["conversation"]["mode"] == "ai"
    assert [(m["direction"], m["body"]) for m in snapshot["messages"]] == [
        ("inbound", "buongiorno"),
        ("outbound", "Ciao! Vuoi prenotare?"),
    ]


def test_handover_notification_is_captured_not_sent(make_env: Any) -> None:
    env = make_env({"intent": "human"})
    turn = env.send("voglio parlare con una persona").json()

    assert "staff" in turn["replies"][0]
    [notification] = turn["operator_notifications"]
    assert "Salone Demo" in notification and PHONE in notification
    assert turn["snapshot"]["conversation"]["mode"] == "manual"

    silent = env.send("ci sei?").json()
    assert silent["replies"] == []
    assert silent["note"] == "Nessuna risposta: la chat è in gestione all'operatore."


def test_resume_ai_and_reset(make_env: Any) -> None:
    env = make_env({"intent": "human"}, {"intent": "greeting", "answer": "Eccomi!"})
    env.send("un operatore per favore")
    target = {"tenant_id": str(env.tenant.id), "phone": PHONE}

    snapshot = env.client.post("/simulator/api/resume-ai", json=target).json()
    assert snapshot["conversation"]["mode"] == "ai"
    assert env.send("ciao").json()["replies"] == ["Eccomi!"]

    assert env.client.post("/simulator/api/reset", json=target).status_code == 204
    after = env.client.get("/simulator/api/conversation", params=target).json()
    assert after == {"conversation": None, "messages": [], "bookings": []}


def test_phone_is_normalized(make_env: Any) -> None:
    env = make_env({"intent": "greeting", "answer": "Ciao!"})
    body = {"tenant_id": str(env.tenant.id), "phone": "39 000 000 0001", "text": "ciao"}
    turn = env.client.post("/simulator/api/messages", json=body).json()
    assert turn["replies"] == ["Ciao!"]
    assert (env.tenant.id, PHONE) in env.store.conversations


def test_simulator_not_mounted_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        production_app = create_app()
        paths = {getattr(r, "path", "") for r in production_app.routes}
        assert not any(p.startswith("/simulator") for p in paths)
        assert TestClient(production_app).get("/simulator").status_code == 404
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


# ---------------------------------------------------------- Google Calendar


def test_google_connect_from_simulator_full_flow(make_env: Any) -> None:
    from urllib.parse import parse_qs, urlparse

    from backend.app.api.deps import get_google_calendar_service
    from backend.tests.google_fake import FakeAdminStore, FakeGoogle, build_service

    env = make_env()
    admin = FakeAdminStore()
    calendar = build_service(FakeGoogle(), admin, allow_dev_flow=True)
    app.dependency_overrides[get_google_calendar_service] = lambda: calendar
    tenant = str(env.tenant.id)

    assert env.client.get("/simulator/api/google", params={"tenant_id": tenant}).json()["connected"] is False
    url = env.client.post("/simulator/api/google/connect", json={"tenant_id": tenant}).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    callback = env.client.get(
        "/oauth/google/callback", params={"code": "auth-code", "state": state}, follow_redirects=False
    )
    assert callback.status_code == 302
    assert callback.headers["location"] == "/simulator?google=connected"
    assert env.client.get("/simulator/api/google", params={"tenant_id": tenant}).json()["connected"] is True

    denied = env.client.get(
        "/oauth/google/callback", params={"error": "access_denied", "state": state}, follow_redirects=False
    )
    assert denied.headers["location"] == "/simulator?google=error&reason=access_denied"

    assert env.client.post("/simulator/api/google/disconnect", json={"tenant_id": tenant}).status_code == 204
    assert admin.credentials == {}


def test_google_connect_requires_configuration(make_env: Any) -> None:
    from backend.app.api.deps import get_google_calendar_service
    from backend.tests.google_fake import FakeAdminStore, FakeGoogle, build_service

    env = make_env()
    app.dependency_overrides[get_google_calendar_service] = lambda: build_service(
        FakeGoogle(), FakeAdminStore(), client_id="", allow_dev_flow=True
    )
    response = env.client.post("/simulator/api/google/connect", json={"tenant_id": str(env.tenant.id)})
    assert response.status_code == 503
    assert "GOOGLE_CLIENT_ID" in response.json()["detail"]
