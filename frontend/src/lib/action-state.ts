/** Esito di una Server Action mostrato dai form (useActionState). */
export type ActionState = {
  error?: string;
  success?: string;
  /** Valori inviati, ripresentati nel form dopo un errore (React 19 azzera i campi). */
  values?: Record<string, string>;
} | null;

export const ok = (success: string): ActionState => ({ success });
export const fail = (error: string): ActionState => ({ error });

export function field(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

/** "+39 333 123 4567" -> "+393331234567"; null se non è un numero plausibile. */
export function normalizePhone(raw: string): string | null {
  const digits = raw.replace(/[^\d]/g, "");
  if (digits.length < 8 || digits.length > 15) return null;
  return `+${digits}`;
}
