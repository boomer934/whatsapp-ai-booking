"use server";

import { refresh } from "next/cache";

import { type ActionState, fail, field, ok } from "@/lib/action-state";
import { getTenantContext } from "@/lib/dal";
import { WEEKDAYS } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";

export type HourRange = { weekday: number; open: string; close: string };

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
const MAX_RANGES_PER_DAY = 4;

function validate(ranges: unknown): HourRange[] | string {
  if (!Array.isArray(ranges)) return "Dati non validi.";
  const parsed: HourRange[] = [];
  for (const r of ranges) {
    if (
      typeof r !== "object" || r === null ||
      typeof r.weekday !== "number" || !Number.isInteger(r.weekday) || r.weekday < 0 || r.weekday > 6 ||
      typeof r.open !== "string" || typeof r.close !== "string" ||
      !TIME.test(r.open) || !TIME.test(r.close)
    ) {
      return "Orario non valido: usa il formato HH:MM.";
    }
    if (r.open >= r.close) {
      return `${WEEKDAYS[r.weekday]}: l'apertura (${r.open}) deve precedere la chiusura (${r.close}).`;
    }
    parsed.push({ weekday: r.weekday, open: r.open, close: r.close });
  }
  for (let day = 0; day < 7; day++) {
    const dayRanges = parsed.filter((r) => r.weekday === day).sort((a, b) => a.open.localeCompare(b.open));
    if (dayRanges.length > MAX_RANGES_PER_DAY) {
      return `${WEEKDAYS[day]}: massimo ${MAX_RANGES_PER_DAY} fasce orarie.`;
    }
    for (let i = 1; i < dayRanges.length; i++) {
      if (dayRanges[i].open < dayRanges[i - 1].close) {
        return `${WEEKDAYS[day]}: le fasce ${dayRanges[i - 1].open}-${dayRanges[i - 1].close} e ${dayRanges[i].open}-${dayRanges[i].close} si sovrappongono.`;
      }
    }
  }
  return parsed;
}

export async function saveHours(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  let raw: unknown;
  try {
    raw = JSON.parse(field(formData, "ranges"));
  } catch {
    return fail("Dati non validi.");
  }
  const ranges = validate(raw);
  if (typeof ranges === "string") return fail(ranges);

  const supabase = await createClient();
  const { data: previous, error: readError } = await supabase
    .from("business_hours")
    .select("id")
    .eq("tenant_id", tenant.id);
  if (readError) return fail(readError.message);

  // Prima si inseriscono le nuove fasce, poi si rimuovono le vecchie:
  // se l'inserimento fallisce gli orari esistenti restano intatti.
  if (ranges.length) {
    const { error } = await supabase.from("business_hours").insert(
      ranges.map((r) => ({ tenant_id: tenant.id, weekday: r.weekday, open_time: r.open, close_time: r.close })),
    );
    if (error) return fail(`Salvataggio non riuscito: ${error.message}`);
  }
  const oldIds = previous.map((p) => p.id);
  if (oldIds.length) {
    const { error } = await supabase
      .from("business_hours")
      .delete()
      .eq("tenant_id", tenant.id)
      .in("id", oldIds);
    if (error) return fail(`Pulizia degli orari precedenti non riuscita: ${error.message}`);
  }
  refresh();
  return ok("Orari salvati: l'assistente userà subito i nuovi orari.");
}
