"""Calcolo degli slot liberi: orari di apertura meno intervalli occupati.

Gli intervalli occupati arrivano da un BusyProvider: oggi le prenotazioni nel DB,
dallo step 7 anche il free/busy di Google Calendar.
"""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.app.models.schemas import BusinessHours, Service, Tenant

PartOfDay = Literal["morning", "afternoon", "evening"]
Interval = tuple[datetime, datetime]

SLOT_STEP = timedelta(minutes=30)
MIN_LEAD_TIME = timedelta(minutes=60)
SEARCH_HORIZON_DAYS = 14

# Fasce orarie (inizio incluso, fine esclusa) per "mattina", "pomeriggio", "sera".
PART_OF_DAY_RANGES: dict[PartOfDay, tuple[time, time]] = {
    "morning": (time(0, 0), time(13, 0)),
    "afternoon": (time(13, 0), time(18, 0)),
    "evening": (time(18, 0), time(23, 59, 59)),
}


class BusyProvider(Protocol):
    async def list_business_hours(self, tenant_id: UUID) -> list[BusinessHours]: ...

    async def list_busy_intervals(
        self, tenant_id: UUID, start: datetime, end: datetime
    ) -> list[Interval]: ...


def is_slot_free(
    start: datetime,
    duration: timedelta,
    hours: Sequence[BusinessHours],
    busy: Sequence[Interval],
    now: datetime,
) -> bool:
    """True se [start, start+duration) è dentro una fascia di apertura, nel futuro
    (con preavviso minimo) e non si sovrappone a intervalli occupati."""
    end = start + duration
    if start < now + MIN_LEAD_TIME or end.date() != start.date():
        return False
    weekday = start.weekday()
    inside_hours = any(
        h.weekday == weekday and h.open_time <= start.time() and end.time() <= h.close_time
        for h in hours
    )
    if not inside_hours:
        return False
    return not any(start < busy_end and busy_start < end for busy_start, busy_end in busy)


def day_slots(
    day: date,
    duration: timedelta,
    hours: Sequence[BusinessHours],
    busy: Sequence[Interval],
    now: datetime,
    tz: ZoneInfo,
) -> list[datetime]:
    """Tutti gli inizi liberi di un giorno, a passi di SLOT_STEP da ogni apertura."""
    slots: list[datetime] = []
    for h in sorted(
        (h for h in hours if h.weekday == day.weekday()), key=lambda h: h.open_time
    ):
        start = datetime.combine(day, h.open_time, tzinfo=tz)
        close = datetime.combine(day, h.close_time, tzinfo=tz)
        while start + duration <= close:
            if is_slot_free(start, duration, hours, busy, now):
                slots.append(start)
            start += SLOT_STEP
    return slots


def _in_part_of_day(slot: datetime, part: PartOfDay | None) -> bool:
    if part is None:
        return True
    lower, upper = PART_OF_DAY_RANGES[part]
    return lower <= slot.time() < upper


class AvailabilityService:
    def __init__(self, provider: BusyProvider) -> None:
        self._provider = provider

    async def find_slots(
        self,
        tenant: Tenant,
        service: Service,
        now: datetime,
        preferred_date: date | None = None,
        preferred_time: time | None = None,
        part_of_day: PartOfDay | None = None,
        limit: int = 3,
    ) -> list[datetime]:
        """Restituisce fino a `limit` inizi liberi, privilegiando le preferenze.

        - Se data e ora richieste sono libere, restituisce solo quello slot.
        - Altrimenti propone gli slot del giorno richiesto più vicini all'ora,
          oppure i primi giorni utili successivi.
        """
        tz = ZoneInfo(tenant.timezone)
        now = now.astimezone(tz)
        duration = timedelta(minutes=service.duration_minutes)
        today = now.date()
        first_day = max(preferred_date or today, today)
        window_start = datetime.combine(first_day, time.min, tzinfo=tz)
        window_end = window_start + timedelta(days=SEARCH_HORIZON_DAYS)

        hours = await self._provider.list_business_hours(tenant.id)
        busy = await self._provider.list_busy_intervals(tenant.id, window_start, window_end)

        if preferred_date and preferred_time:
            exact = datetime.combine(preferred_date, preferred_time, tzinfo=tz)
            if is_slot_free(exact, duration, hours, busy, now):
                return [exact]

        found: list[datetime] = []
        for offset in range(SEARCH_HORIZON_DAYS):
            day = first_day + timedelta(days=offset)
            candidates = [
                s
                for s in day_slots(day, duration, hours, busy, now, tz)
                if _in_part_of_day(s, part_of_day)
            ]
            # Ora preferita: nel primo giorno utile (quello richiesto, se libero)
            # propone gli slot più vicini a quell'ora.
            if preferred_time is not None and candidates:
                target = datetime.combine(day, preferred_time, tzinfo=tz)
                closest = sorted(candidates, key=lambda s: (abs(s - target), s))[:limit]
                return sorted(closest)
            found.extend(candidates[: limit - len(found)])
            if len(found) >= limit:
                break
        return found
