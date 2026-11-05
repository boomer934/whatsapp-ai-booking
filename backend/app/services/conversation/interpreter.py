"""Interpretazione dei messaggi con l'LLM e validazione dell'output."""

import logging
from datetime import date, datetime, time
from enum import StrEnum
from typing import Any, get_args

from pydantic import BaseModel, TypeAdapter, ValidationError

from backend.app.models.enums import ConversationState
from backend.app.models.schemas import BusinessHours, Service, Tenant
from backend.app.services.calendar.availability import PartOfDay
from backend.app.services.conversation.context import BookingContext
from backend.app.services.llm.base import LLMClient, LLMError
from backend.app.services.llm.prompts import build_system_prompt, build_user_prompt

logger = logging.getLogger(__name__)

MAX_ANSWER_CHARS = 400


class Intent(StrEnum):
    BOOKING_REQUEST = "booking_request"
    CONFIRM = "confirm"
    DECLINE = "decline"
    QUESTION = "question"
    GREETING = "greeting"
    HUMAN = "human"
    UNCLEAR = "unclear"


class Interpretation(BaseModel):
    intent: Intent
    service: Service | None = None
    day: date | None = None
    at: time | None = None
    part_of_day: PartOfDay | None = None
    slot_number: int | None = None
    answer: str | None = None

    @property
    def has_time_preference(self) -> bool:
        return any(v is not None for v in (self.day, self.at, self.part_of_day, self.slot_number))

    @property
    def has_booking_details(self) -> bool:
        return any(
            v is not None
            for v in (self.service, self.day, self.at, self.part_of_day, self.slot_number)
        )


class InterpretationError(RuntimeError):
    """L'LLM non è disponibile o ha restituito dati inutilizzabili."""


_DATE = TypeAdapter(date)
_TIME = TypeAdapter(time)


def _safe(adapter: TypeAdapter[Any], value: Any) -> Any:
    """Valida un singolo campo: un valore malformato diventa None invece di
    invalidare l'intera risposta."""
    if value in (None, ""):
        return None
    try:
        return adapter.validate_python(value)
    except ValidationError:
        return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def parse_llm_output(
    raw: dict[str, Any], services: list[Service], today: date
) -> Interpretation:
    """Converte l'output grezzo del modello in un'Interpretation validata."""
    try:
        intent = Intent(str(raw.get("intent", "")).strip().lower())
    except ValueError:
        intent = Intent.UNCLEAR

    service_number = _safe_int(raw.get("service_number"))
    service = (
        services[service_number - 1]
        if service_number is not None and 1 <= service_number <= len(services)
        else None
    )

    day = _safe(_DATE, raw.get("date"))
    if day is not None and day < today:
        day = None

    part = raw.get("part_of_day")
    part_of_day = part if part in get_args(PartOfDay) else None

    answer = raw.get("answer")
    if intent not in (Intent.QUESTION, Intent.GREETING) or not isinstance(answer, str):
        answer = None
    else:
        answer = answer.strip()[:MAX_ANSWER_CHARS] or None

    return Interpretation(
        intent=intent,
        service=service,
        day=day,
        at=_safe(_TIME, raw.get("time")),
        part_of_day=part_of_day,
        slot_number=_safe_int(raw.get("slot_number")),
        answer=answer,
    )


class MessageInterpreter:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def interpret(
        self,
        *,
        tenant: Tenant,
        services: list[Service],
        hours: list[BusinessHours],
        state: ConversationState,
        context: BookingContext,
        text: str,
        now: datetime,
    ) -> Interpretation:
        """`now` deve essere nel fuso orario del tenant."""
        system_prompt = build_system_prompt(tenant, services, hours, state, context, now)
        try:
            raw = await self._llm.complete_json(system_prompt, build_user_prompt(text))
        except LLMError as exc:
            raise InterpretationError(str(exc)) from exc
        interpretation = parse_llm_output(raw, services, now.date())
        logger.debug("Interpretazione: %s", interpretation.model_dump(exclude={"service"}))
        return interpretation
