"use server";

import { refresh } from "next/cache";

import { type ActionState, fail, field, ok } from "@/lib/action-state";
import { getTenantContext } from "@/lib/dal";
import { createClient } from "@/lib/supabase/server";

type ServiceInput = { name: string; duration_minutes: number; price_cents: number | null };

/** "35" | "35,50" | "35.5" | "" -> centesimi (null se vuoto). */
function parsePrice(raw: string): number | null | "invalid" {
  if (!raw) return null;
  const normalized = raw.replace("€", "").replace(",", ".").trim();
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return "invalid";
  return Math.round(Number(normalized) * 100);
}

function parseService(formData: FormData): ServiceInput | string {
  const name = field(formData, "name");
  const duration = Number(field(formData, "duration_minutes"));
  const price = parsePrice(field(formData, "price"));
  if (name.length < 1 || name.length > 120) return "Inserisci il nome del servizio.";
  if (!Number.isInteger(duration) || duration < 5 || duration > 600)
    return "La durata deve essere tra 5 e 600 minuti.";
  if (price === "invalid") return "Prezzo non valido (es. 25 oppure 25,50).";
  return { name, duration_minutes: duration, price_cents: price };
}

export async function createService(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  const input = parseService(formData);
  if (typeof input === "string") return fail(input);
  const supabase = await createClient();
  const { error } = await supabase.from("services").insert({ ...input, tenant_id: tenant.id });
  if (error) return fail(`Salvataggio non riuscito: ${error.message}`);
  refresh();
  return ok(`"${input.name}" aggiunto.`);
}

export async function updateService(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  const id = field(formData, "id");
  const input = parseService(formData);
  if (typeof input === "string") return fail(input);
  const supabase = await createClient();
  const { error } = await supabase
    .from("services")
    .update(input)
    .eq("id", id)
    .eq("tenant_id", tenant.id);
  if (error) return fail(`Salvataggio non riuscito: ${error.message}`);
  refresh();
  return ok("Modifiche salvate.");
}

export async function setServiceActive(id: string, active: boolean): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  const supabase = await createClient();
  const { error } = await supabase
    .from("services")
    .update({ is_active: active })
    .eq("id", id)
    .eq("tenant_id", tenant.id);
  if (error) return fail(error.message);
  refresh();
  return ok(active ? "Servizio attivato." : "Servizio disattivato.");
}

export async function deleteService(id: string): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  const supabase = await createClient();
  // Le prenotazioni esistenti restano (service_id diventa NULL).
  const { error } = await supabase.from("services").delete().eq("id", id).eq("tenant_id", tenant.id);
  if (error) return fail(error.message);
  refresh();
  return ok("Servizio eliminato.");
}
