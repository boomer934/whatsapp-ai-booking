"""Formattazione in italiano di date, prezzi e servizi per WhatsApp.

Nessuna dipendenza dal locale di sistema (che su Render non è garantito).
"""

from datetime import date, datetime

from backend.app.models.schemas import BusinessHours, Service

WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
WEEKDAYS_SHORT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MONTHS = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def format_day(day: date) -> str:
    """Es. 'giovedì 6 novembre'."""
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"


def format_slot(start: datetime) -> str:
    """Es. 'giovedì 6 novembre alle 15:00' (start nel fuso del tenant)."""
    return f"{format_day(start.date())} alle {start:%H:%M}"


def format_slot_short(start: datetime) -> str:
    """Es. 'gio 6/11 ore 15:00', per gli elenchi numerati."""
    return f"{WEEKDAYS_SHORT[start.weekday()]} {start.day}/{start.month} ore {start:%H:%M}"


def format_price(price_cents: int | None) -> str | None:
    if price_cents is None:
        return None
    euros, cents = divmod(price_cents, 100)
    return f"{euros} €" if cents == 0 else f"{euros},{cents:02d} €"


def format_service(service: Service) -> str:
    details = [f"{service.duration_minutes} min"]
    price = format_price(service.price_cents)
    if price:
        details.append(price)
    return f"{service.name} ({', '.join(details)})"


def format_service_list(services: list[Service]) -> str:
    return "\n".join(f"{i}. {format_service(s)}" for i, s in enumerate(services, start=1))


def format_slot_list(slots: list[datetime]) -> str:
    return "\n".join(f"{i}. {format_slot_short(s)}" for i, s in enumerate(slots, start=1))


def format_business_hours(hours: list[BusinessHours]) -> str:
    """Es. 'martedì: 09:00-13:00, 14:30-19:00' una riga per giorno."""
    lines: list[str] = []
    for weekday, name in enumerate(WEEKDAYS):
        ranges = sorted(
            (h.open_time, h.close_time) for h in hours if h.weekday == weekday
        )
        text = ", ".join(f"{o:%H:%M}-{c:%H:%M}" for o, c in ranges) if ranges else "chiuso"
        lines.append(f"{name}: {text}")
    return "\n".join(lines)
