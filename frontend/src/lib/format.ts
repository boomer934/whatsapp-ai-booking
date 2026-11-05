/** Formattazione in italiano, sempre nel fuso orario dell'attività. */

export const WEEKDAYS = [
  "Lunedì",
  "Martedì",
  "Mercoledì",
  "Giovedì",
  "Venerdì",
  "Sabato",
  "Domenica",
] as const;

export function formatDateTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    timeZone,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("it-IT", { timeZone, hour: "2-digit", minute: "2-digit" }).format(
    new Date(iso),
  );
}

export function formatDay(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    timeZone,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(iso));
}

/** "dd/mm hh:mm" compatto per elenchi. */
export function formatShort(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatPrice(cents: number | null): string {
  if (cents === null) return "—";
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(cents / 100);
}

/** "09:00:00" (Postgres time) -> "09:00" */
export function trimTime(value: string): string {
  return value.slice(0, 5);
}

export const STATE_LABELS: Record<string, string> = {
  idle: "In attesa",
  selecting_service: "Sceglie il servizio",
  selecting_slot: "Sceglie l'orario",
  confirming: "Deve confermare",
  completed: "Prenotazione completata",
};
