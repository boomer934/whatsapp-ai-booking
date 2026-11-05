"use server";

import { refresh } from "next/cache";

import { type ActionState, fail, ok } from "@/lib/action-state";
import { getTenantContext } from "@/lib/dal";
import { createClient } from "@/lib/supabase/server";

/** Accende/spegne l'assistente AI dell'attività. */
export async function setAiEnabled(enabled: boolean): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  const supabase = await createClient();
  const { error } = await supabase
    .from("tenants")
    .update({ ai_enabled: enabled })
    .eq("id", tenant.id);
  if (error) return fail(`Aggiornamento non riuscito: ${error.message}`);
  refresh();
  return ok(enabled ? "Assistente attivato." : "Assistente disattivato.");
}

/** Riporta una conversazione dall'operatore all'AI. */
export async function resumeAi(conversationId: string): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  const supabase = await createClient();
  const { error, count } = await supabase
    .from("conversations")
    .update({ mode: "ai", failed_attempts: 0 }, { count: "exact" })
    .eq("id", conversationId)
    .eq("tenant_id", tenant.id);
  if (error) return fail(`Operazione non riuscita: ${error.message}`);
  if (!count) return fail("Conversazione non trovata.");
  refresh();
  return ok("L'assistente ha ripreso la conversazione.");
}
