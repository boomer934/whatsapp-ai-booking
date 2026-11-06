"use server";

import { redirect } from "next/navigation";

import { type ActionState, fail, field } from "@/lib/action-state";
import { createClient } from "@/lib/supabase/server";

/** Solo percorsi interni: evita open redirect verso siti esterni. */
function safeNext(value: string): string {
  return value.startsWith("/") && !value.startsWith("//") ? value : "/dashboard";
}

function translateAuthError(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("invalid login credentials")) return "Email o password non corretti.";
  if (m.includes("email not confirmed"))
    return "Devi prima confermare l'email: controlla la posta (anche lo spam).";
  if (m.includes("already registered") || m.includes("already been registered"))
    return "Esiste già un account con questa email: accedi.";
  if (m.includes("password")) return "Password non valida: usa almeno 8 caratteri.";
  if (m.includes("email rate limit"))
    return "Abbiamo raggiunto il limite di email di conferma inviabili: riprova tra un'ora.";
  if (m.includes("rate limit") || m.includes("too many"))
    return "Troppi tentativi: riprova tra qualche minuto.";
  return message;
}

export async function signIn(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const email = field(formData, "email");
  const password = field(formData, "password");
  if (!email || !password) return fail("Inserisci email e password.");

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return fail(translateAuthError(error.message));
  redirect(safeNext(field(formData, "next")));
}

export async function signOut(): Promise<void> {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
