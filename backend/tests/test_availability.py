import asyncio
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.app.models.schemas import BusinessHours
from backend.app.services.calendar.availability import AvailabilityService, day_slots, is_slot_free
from backend.tests.fakes import make_service, make_tenant, weekly_hours

ROME = ZoneInfo("Europe/Rome")
# Giovedì 5 novembre 2026, ore 10:00 a Roma.
NOW = datetime(2026, 11, 5, 10, 0, tzinfo=ROME)
FRIDAY = date(2026, 11, 6)
SUNDAY = date(2026, 11, 8)


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=ROME)


class Provider:
    def __init__(self, busy: list[tuple[datetime, datetime]] | None = None) -> None:
        self.busy = busy or []

    async def list_business_hours(self, tenant_id: UUID) -> list[BusinessHours]:
        return weekly_hours()

    async def list_busy_intervals(
        self, tenant_id: UUID, start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        return self.busy


def find(busy: list[tuple[datetime, datetime]] | None = None, minutes: int = 30, **kwargs: object) -> list[datetime]:
    tenant = make_tenant()
    service = make_service(tenant.id, "Taglio", minutes, 2000)
    return asyncio.run(
        AvailabilityService(Provider(busy)).find_slots(tenant, service, NOW, **kwargs)  # type: ignore[arg-type]
    )


def test_is_slot_free_rules() -> None:
    hours = weekly_hours()
    half_hour = timedelta(minutes=30)
    assert is_slot_free(at(FRIDAY, 9), half_hour, hours, [], NOW)
    assert not is_slot_free(at(FRIDAY, 12, 45), half_hour, hours, [], NOW)  # sfora la chiusura
    assert not is_slot_free(at(FRIDAY, 13, 30), half_hour, hours, [], NOW)  # pausa pranzo
    assert not is_slot_free(at(SUNDAY, 10), half_hour, hours, [], NOW)  # chiuso
    assert not is_slot_free(at(NOW.date(), 10, 30), half_hour, hours, [], NOW)  # preavviso < 60'
    busy = [(at(FRIDAY, 9, 15), at(FRIDAY, 9, 45))]
    assert not is_slot_free(at(FRIDAY, 9), half_hour, hours, busy, NOW)
    assert is_slot_free(at(FRIDAY, 9, 45), half_hour, hours, busy, NOW)


def test_day_slots_respect_breaks() -> None:
    slots = day_slots(FRIDAY, timedelta(minutes=90), weekly_hours(), [], NOW, ROME)
    assert slots[0] == at(FRIDAY, 9)
    assert at(FRIDAY, 11, 30) in slots and at(FRIDAY, 12) not in slots
    assert at(FRIDAY, 14, 30) in slots and slots[-1] == at(FRIDAY, 17, 30)


def test_exact_requested_slot_is_returned_alone() -> None:
    assert find(preferred_date=FRIDAY, preferred_time=time(15)) == [at(FRIDAY, 15)]


def test_busy_requested_slot_returns_closest_alternatives() -> None:
    busy = [(at(FRIDAY, 15), at(FRIDAY, 16))]
    slots = find(busy, preferred_date=FRIDAY, preferred_time=time(15))
    assert slots == [at(FRIDAY, 14, 30), at(FRIDAY, 16), at(FRIDAY, 16, 30)]


def test_no_preferences_returns_first_free_slots_from_now() -> None:
    assert find() == [at(NOW.date(), 11), at(NOW.date(), 11, 30), at(NOW.date(), 12)]


def test_part_of_day_filter() -> None:
    slots = find(preferred_date=FRIDAY, part_of_day="afternoon")
    assert slots == [at(FRIDAY, 14, 30), at(FRIDAY, 15), at(FRIDAY, 15, 30)]


def test_closed_day_moves_to_next_open_day() -> None:
    slots = find(preferred_date=SUNDAY)
    assert slots[0] == at(date(2026, 11, 10), 9)  # domenica e lunedì chiusi -> martedì
