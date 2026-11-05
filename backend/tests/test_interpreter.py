import asyncio
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from backend.app.models.enums import ConversationState
from backend.app.services.conversation.context import BookingContext
from backend.app.services.conversation.interpreter import (
    Intent,
    InterpretationError,
    MessageInterpreter,
    parse_llm_output,
)
from backend.app.services.llm.base import LLMError
from backend.tests.fakes import ScriptedLLM, make_service, make_tenant, weekly_hours

ROME = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 11, 5, 10, 0, tzinfo=ROME)
TENANT = make_tenant()
SERVICES = [
    make_service(TENANT.id, "Taglio donna", 45, 3500),
    make_service(TENANT.id, "Colore", 90, 6000),
]


def test_parse_full_booking_request() -> None:
    result = parse_llm_output(
        {
            "intent": "booking_request",
            "service_number": 2,
            "date": "2026-11-06",
            "time": "15:00",
            "part_of_day": None,
            "slot_number": None,
            "answer": "ignorata",
        },
        SERVICES,
        NOW.date(),
    )
    assert result.intent == Intent.BOOKING_REQUEST
    assert result.service == SERVICES[1]
    assert result.day == date(2026, 11, 6)
    assert result.at == time(15, 0)
    assert result.answer is None  # answer solo per question/greeting


@pytest.mark.parametrize(
    ("raw", "field", "expected"),
    [
        ({"intent": "booking_request", "service_number": 9}, "service", None),
        ({"intent": "booking_request", "service_number": "1"}, "service", SERVICES[0]),
        ({"intent": "booking_request", "date": "2026-02-30"}, "day", None),
        ({"intent": "booking_request", "date": "2026-11-01"}, "day", None),  # nel passato
        ({"intent": "booking_request", "time": "25:99"}, "at", None),
        ({"intent": "booking_request", "part_of_day": "notte"}, "part_of_day", None),
        ({"intent": "boh"}, "intent", Intent.UNCLEAR),
        ({}, "intent", Intent.UNCLEAR),
        ({"intent": "QUESTION", "answer": "  Costa 35 €.  "}, "answer", "Costa 35 €."),
    ],
)
def test_parse_is_lenient_per_field(raw: dict[str, object], field: str, expected: object) -> None:
    assert getattr(parse_llm_output(raw, SERVICES, NOW.date()), field) == expected


def test_prompt_contains_business_data_and_state() -> None:
    llm = ScriptedLLM({"intent": "booking_request", "slot_number": 1})
    context = BookingContext(
        service_id=SERVICES[0].id,
        proposed_slots=[datetime(2026, 11, 6, 15, 0, tzinfo=ROME)],
    )
    asyncio.run(
        MessageInterpreter(llm).interpret(
            tenant=TENANT,
            services=SERVICES,
            hours=weekly_hours(),
            state=ConversationState.SELECTING_SLOT,
            context=context,
            text="il primo",
            now=NOW,
        )
    )
    system_prompt, user_prompt = llm.prompts[0]
    assert "1. Taglio donna (45 min, 35 €)" in system_prompt
    assert "- oggi giovedì 2026-11-05" in system_prompt
    assert "- domani venerdì 2026-11-06" in system_prompt
    assert "martedì: 09:00-13:00, 14:30-19:00" in system_prompt
    assert "lunedì: chiuso" in system_prompt
    assert "Servizio già scelto: Taglio donna." in system_prompt
    assert "1. ven 6/11 ore 15:00" in system_prompt
    assert "il primo" in user_prompt


def test_llm_error_becomes_interpretation_error() -> None:
    interpreter = MessageInterpreter(ScriptedLLM(LLMError("timeout")))
    with pytest.raises(InterpretationError):
        asyncio.run(
            interpreter.interpret(
                tenant=TENANT,
                services=SERVICES,
                hours=[],
                state=ConversationState.IDLE,
                context=BookingContext(),
                text="ciao",
                now=NOW,
            )
        )
