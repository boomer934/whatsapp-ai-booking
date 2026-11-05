import "server-only";

import { redirect } from "next/navigation";
import { cache } from "react";

import type { MemberRole, TenantRow } from "@/lib/database.types";
import { createClient } from "@/lib/supabase/server";

/**
 * Data Access Layer: unico punto in cui si verifica la sessione e si risolve
 * l'attività dell'utente. Da richiamare in ogni pagina e in ogni Server Action
 * (le azioni non devono mai fidarsi di id passati dal client).
 */

export type CurrentUser = { id: string; email: string | null };

export type TenantContext = {
  user: CurrentUser;
  tenant: TenantRow;
  role: MemberRole;
};

export const getCurrentUser = cache(async (): Promise<CurrentUser> => {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  const claims = data?.claims;
  if (!claims?.sub) {
    redirect("/login");
  }
  return { id: claims.sub, email: typeof claims.email === "string" ? claims.email : null };
});

/** Attività dell'utente (MVP: la prima di cui è membro). Senza attività -> onboarding. */
export const getTenantContext = cache(async (): Promise<TenantContext> => {
  const user = await getCurrentUser();
  const supabase = await createClient();

  const { data: membership, error } = await supabase
    .from("tenant_members")
    .select("tenant_id, role")
    .eq("user_id", user.id)
    .order("created_at")
    .limit(1)
    .maybeSingle();
  if (error) {
    throw new Error(`Impossibile leggere l'attività: ${error.message}`);
  }
  if (!membership) {
    redirect("/onboarding");
  }

  const { data: tenant, error: tenantError } = await supabase
    .from("tenants")
    .select("*")
    .eq("id", membership.tenant_id)
    .single();
  if (tenantError || !tenant) {
    throw new Error(`Attività non trovata: ${tenantError?.message ?? "nessun dato"}`);
  }
  return { user, tenant, role: membership.role };
});
