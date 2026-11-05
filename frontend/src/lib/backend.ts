import "server-only";

import { createClient } from "@/lib/supabase/server";

/**
 * Chiamate al backend FastAPI con il token di sessione dell'utente.
 * Il backend verifica il token con Supabase Auth e l'appartenenza all'attività.
 */

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class BackendError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function backendFetch<T>(path: string, init: RequestInit = {}): Promise<T | null> {
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
      headers: {
        ...init.headers,
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
      },
    });
  } catch {
    throw new BackendError("Backend non raggiungibile: è avviato su " + API_URL + "?", 503);
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
