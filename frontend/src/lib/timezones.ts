/** Fusi orari proposti nei form (l'attività riceve clienti nel proprio fuso). */
export const TIMEZONES = [
  { value: "Europe/Rome", label: "Italia (Europe/Rome)" },
  { value: "Europe/Zurich", label: "Svizzera (Europe/Zurich)" },
  { value: "Europe/Paris", label: "Francia (Europe/Paris)" },
  { value: "Europe/Madrid", label: "Spagna (Europe/Madrid)" },
  { value: "Europe/Berlin", label: "Germania (Europe/Berlin)" },
  { value: "Europe/London", label: "Regno Unito (Europe/London)" },
  { value: "Europe/Lisbon", label: "Portogallo (Europe/Lisbon)" },
  { value: "Europe/Athens", label: "Grecia (Europe/Athens)" },
  { value: "Europe/Bucharest", label: "Romania (Europe/Bucharest)" },
  { value: "America/New_York", label: "USA Est (America/New_York)" },
] as const;

export function isValidTimezone(value: string): boolean {
  try {
    new Intl.DateTimeFormat("it-IT", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}
