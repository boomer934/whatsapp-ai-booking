import "server-only";

import { createClient } from "@/lib/supabase/server";

/**
 * Chiamate al backend FastAPI con il token di sessione dell'utente.
 * Il backend verifica il token con Supabase Auth e l'appartenenza all'attività.
 */

// Su Vercel API_URL è obbligatorio: senza, le chiamate (con il token dell'utente)
// finirebbero su localhost. In locale il default è il backend su :8000.
const API_URL = process.env.API_URL ?? (process.env.VERCEL ? undefined : "http://localhost:8000");

/** Render (piano Free) si sospende dopo 15 minuti: il risveglio può durare ~50 secondi. */
const DEFAULT_TIMEOUT_MS = 60_000;

export class BackendError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function backendFetch<T>(
  path: string,
  init: RequestInit = {},
  { timeoutMs = DEFAULT_TIMEOUT_MS }: { timeoutMs?: number } = {},
): Promise<T | null> {
  if (!API_URL) {
    throw new BackendError("Backend non configurato (API_URL mancante).", 500);
  }
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    throw new BackendError("Sessione scaduta: accedi di nuovo.", 401);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
      headers: {
        ...init.headers,
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new BackendError("Il server si sta avviando: riprova tra qualche secondo.", 504);
    }
    throw new BackendError("Backend non raggiungibile: riprova tra poco.", 503);
  }

  if (response.status === 204) {
    return null;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body && typeof body.detail === "string"
        ? body.detail
        : `Errore ${response.status}`;
    throw new BackendError(detail, response.status);
  }
  return body as T;
}
