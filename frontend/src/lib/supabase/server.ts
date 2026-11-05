import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import type { Database } from "@/lib/database.types";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "@/lib/env";

/**
 * Client Supabase per Server Components, Server Actions e Route Handlers.
 * Usa la sessione dell'utente: ogni query è soggetta alla RLS.
 * Va creato per ogni richiesta (mai condiviso).
 */
export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient<Database>(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Chiamato da un Server Component: i cookie si possono scrivere solo in
          // Server Actions e Route Handlers. Il refresh della sessione lo fa il proxy.
        }
      },
    },
  });
}
