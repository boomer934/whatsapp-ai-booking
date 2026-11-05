"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { type ActionState, fail, field, normalizePhone, ok } from "@/lib/action-state";
import { BackendError, backendFetch } from "@/lib/backend";
import { getTenantContext } from "@/lib/dal";
import { createClient } from "@/lib/supabase/server";
import { isValidTimezone } from "@/lib/timezones";

export async function updateTenant(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  const name = field(formData, "name");
  const timezone = field(formData, "timezone");
  const rawPhone = field(formData, "operator_phone");
  if (name.length < 2 || name.length > 120) return fail("Inserisci il nome dell'attività.");
  if (!isValidTimezone(timezone)) return fail("Fuso orario non valido.");
  const operatorPhone = rawPhone ? normalizePhone(rawPhone) : null;
  if (rawPhone && !operatorPhone) return fail("Numero dell'operatore non valido (es. +39 333 1234567).");

  const supabase = await createClient();
  const { error } = await supabase
    .from("tenants")
    .update({ name, timezone, operator_phone: operatorPhone })
    .eq("id", tenant.id);
  if (error) return fail(`Salvataggio non riuscito: ${error.message}`);
  refresh();
  return ok("Impostazioni salvate.");
}

export async function connectGoogle(): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  let url: string;
  try {
    const result = await backendFetch<{ authorization_url: string }>(
      `/api/tenants/${tenant.id}/google/connect`,
      { method: "POST" },
    );
    if (!result) return fail("Risposta del backend non valida.");
    url = result.authorization_url;
  } catch (error) {
    return fail(error instanceof BackendError ? error.message : "Collegamento non riuscito.");
  }
  // Fuori dal try: redirect() interrompe l'esecuzione lanciando un'eccezione.
  redirect(url);
}

export async function disconnectGoogle(): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  try {
    await backendFetch(`/api/tenants/${tenant.id}/google`, { method: "DELETE" });
  } catch (error) {
    return fail(error instanceof BackendError ? error.message : "Scollegamento non riuscito.");
  }
  refresh();
  return ok("Google Calendar scollegato.");
}
