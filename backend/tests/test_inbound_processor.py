import asyncio

from backend.app.models.enums import ConversationMode, MessagingProviderName
from backend.app.models.schemas import Conversation, InboundMessage, Tenant
from backend.app.services.conversation.inbound import InboundProcessor
from backend.tests.fakes import FakeSender, FakeStore, make_message, make_tenant


class EchoEngine:
    async def reply(
        self, tenant: Tenant, conversation: Conversation, message: InboundMessage
    ) -> str | None:
        return f"eco: {message.text}"


def build(store: FakeStore) -> tuple[InboundProcessor, FakeSender]:
    sender = FakeSender()
    processor = InboundProcessor(
        store=store,
        engine=EchoEngine(),
        senders={MessagingProviderName.META: sender, MessagingProviderName.TWILIO: sender},
    )
    return processor, sender


def test_new_message_gets_reply_and_is_stored() -> None:
    store = FakeStore([make_tenant()])
    processor, sender = build(store)

    asyncio.run(processor.process(make_message()))

    assert len(sender.sent) == 1
    assert sender.sent[0][1] == "+393331112222"
    assert len(store.outbound) == 1
    assert store.outbound[0][2] == "sent-1"


def test_duplicate_webhook_is_ignored() -> None:
    store = FakeStore([make_tenant()])
    processor, sender = build(store)

    asyncio.run(processor.process(make_message()))
    asyncio.run(processor.process(make_message()))

    assert len(sender.sent) == 1


def test_unknown_tenant_is_dropped() -> None:
    store = FakeStore([make_tenant()])
    processor, sender = build(store)

    asyncio.run(processor.process(make_message(routing_key="ALTRO")))

    assert sender.sent == []
    assert store.conversations == {}


def test_ai_disabled_stores_but_does_not_reply() -> None:
    store = FakeStore([make_tenant(ai_enabled=False)])
    processor, sender = build(store)

    asyncio.run(processor.process(make_message()))

    assert len(store.inbound_ids) == 1
    assert sender.sent == []


def test_manual_mode_does_not_reply() -> None:
    tenant = make_tenant()
    store = FakeStore([tenant])
    processor, sender = build(store)
    conversation = asyncio.run(
        store.get_or_create_conversation(tenant.id, "+393331112222", None)
    )
    conversation.mode = ConversationMode.MANUAL

    asyncio.run(processor.process(make_message()))

    assert len(store.inbound_ids) == 1
    assert sender.sent == []


def test_same_phone_on_two_tenants_creates_separate_conversations() -> None:
    tenant_a = make_tenant(wa_phone_number_id="PNID-A")
    tenant_b = make_tenant(wa_phone_number_id="PNID-B")
    store = FakeStore([tenant_a, tenant_b])
    processor, _ = build(store)

    asyncio.run(processor.process(make_message(routing_key="PNID-A")))
    asyncio.run(processor.process(make_message(routing_key="PNID-B")))

    assert {key[0] for key in store.conversations} == {tenant_a.id, tenant_b.id}


def test_process_safely_swallows_errors() -> None:
    class BrokenStore(FakeStore):
        async def get_tenant_by_routing_key(self, provider, routing_key):  # type: ignore[no-untyped-def]
            raise RuntimeError("DB giù")

    processor, _ = build(BrokenStore([]))
    asyncio.run(processor.process_safely(make_message()))  # non deve sollevare
