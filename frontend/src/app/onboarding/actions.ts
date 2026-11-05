"use server";

import { redirect } from "next/navigation";

import { type ActionState, fail, field } from "@/lib/action-state";
import { getCurrentUser } from "@/lib/dal";
import { createClient } from "@/lib/supabase/server";
import { isValidTimezone } from "@/lib/timezones";

export async function createTenant(_prev: ActionState, formData: FormData): Promise<ActionState> {
  await getCurrentUser();
  const name = field(formData, "name");
  const timezone = field(formData, "timezone") || "Europe/Rome";
  if (name.length < 2 || name.length > 120) return fail("Inserisci il nome dell'attività.");
  if (!isValidTimezone(timezone)) return fail("Fuso orario non valido.");

  const supabase = await createClient();
  // RPC atomica: crea l'attività e rende l'utente titolare (vedi 0002_rls_policies.sql).
  const { error } = await supabase.rpc("create_tenant", { p_name: name, p_timezone: timezone });
  if (error) return fail(`Creazione non riuscita: ${error.message}`);
  redirect("/dashboard");
}
