import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Badge, Card, EmptyState, PageHeader, Skeleton, buttonClass } from "@/components/ui";
import { backendFetch } from "@/lib/backend";
import { getTenantContext } from "@/lib/dal";
import { addDays, startOfDayInZone } from "@/lib/dates";
import { formatDateTime, formatShort } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";

import { AiToggle } from "./ai-toggle";

export const metadata: Metadata = { title: "Panoramica" };

export default function OverviewPage() {
  return (
    <>
      <PageHeader title="Panoramica" description="Lo stato del tuo assistente WhatsApp in un colpo d'occhio." />
      <Suspense fallback={<Skeleton rows={5} />}>
        <Overview />
      </Suspense>
    </>
  );
}

type GoogleStatus = { connected: boolean };

async function Overview() {
  const { tenant } = await getTenantContext();
  const supabase = await createClient();
  const now = new Date();
  const todayStart = startOfDayInZone(now, tenant.timezone);

  const [services, hours, todayBookings, upcoming, manualChats, google] = await Promise.all([
    supabase.from("services").select("id", { count: "exact", head: true }).eq("tenant_id", tenant.id).eq("is_active", true),
    supabase.from("business_hours").select("id", { count: "exact", head: true }).eq("tenant_id", tenant.id),
    supabase
      .from("bookings")
      .select("id", { count: "exact", head: true })
      .eq("tenant_id", tenant.id)
      .eq("status", "confirmed")
      .gte("starts_at", todayStart.toISOString())
      .lt("starts_at", addDays(todayStart, 1).toISOString()),
    supabase
      .from("bookings")
      .select("id, starts_at, customer_name, customer_phone, service_id")
      .eq("tenant_id", tenant.id)
      .eq("status", "confirmed")
      .gte("starts_at", now.toISOString())
      .order("starts_at")
      .limit(5),
    supabase
      .from("conversations")
      .select("id, customer_name, customer_phone, last_message_at")
      .eq("tenant_id", tenant.id)
      .eq("mode", "manual")
      .order("last_message_at", { ascending: false })
      .limit(5),
    backendFetch<GoogleStatus>(`/api/tenants/${tenant.id}/google`).catch(() => null),
  ]);

  const serviceNames = await loadServiceNames(tenant.id, upcoming.data?.map((b) => b.service_id));
  const setup = [
    { done: (services.count ?? 0) > 0, label: "Aggiungi almeno un servizio", href: "/dashboard/services" },
    { done: (hours.count ?? 0) > 0, label: "Imposta gli orari di apertura", href: "/dashboard/hours" },
    { done: Boolean(tenant.operator_phone), label: "Indica il numero dell'operatore", href: "/dashboard/settings" },
    { done: Boolean(google?.connected), label: "Collega Google Calendar (consigliato)", href: "/dashboard/settings" },
  ];
  const missing = setup.filter((s) => !s.done);
  // Attività appena creata: nessun servizio e nessun orario ancora configurati.
  const isNew = !setup[0].done && !setup[1].done;

  return (
    <div className="space-y-6">
      {isNew ? (
        <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          🎉 Benvenuto! Completa i passaggi qui sotto per attivare le prenotazioni su WhatsApp.
        </p>
      ) : null}

      <Card title="Assistente AI">
        <AiToggle enabled={tenant.ai_enabled} />
      </Card>

      {missing.length ? (
        <Card title="Da completare">
          <ul className="space-y-2">
            {setup.map((s) => (
              <li key={s.label} className="flex items-center gap-3 text-sm">
                <span aria-hidden>{s.done ? "✅" : "⬜️"}</span>
                {s.done ? (
                  <span className="text-slate-400 line-through">{s.label}</span>
                ) : (
                  <Link href={s.href} className={buttonClass.link}>
                    {s.label}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Appuntamenti oggi" value={todayBookings.count ?? 0} />
        <Stat label="Prossimi appuntamenti" value={upcoming.data?.length ?? 0} suffix={upcoming.data?.length === 5 ? "+" : ""} />
        <Stat label="Chat in attesa dell'operatore" value={manualChats.data?.length ?? 0} tone={manualChats.data?.length ? "red" : "slate"} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Prossimi appuntamenti">
          {upcoming.data?.length ? (
            <ul className="divide-y divide-slate-100">
              {upcoming.data.map((b) => (
                <li key={b.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <div>
                    <p className="font-medium">{b.customer_name ?? b.customer_phone}</p>
                    <p className="text-slate-500">{serviceNames.get(b.service_id ?? "") ?? "Servizio"}</p>
                  </div>
                  <span className="text-right text-slate-700">{formatDateTime(b.starts_at, tenant.timezone)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>Nessun appuntamento in programma.</EmptyState>
          )}
          <Link href="/dashboard/bookings" className={`mt-4 inline-block ${buttonClass.link}`}>
            Tutte le prenotazioni →
          </Link>
        </Card>

        <Card title="Chat da gestire">
          {manualChats.data?.length ? (
            <ul className="divide-y divide-slate-100">
              {manualChats.data.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <div>
                    <p className="font-medium">{c.customer_name ?? c.customer_phone}</p>
                    <p className="text-slate-500">
                      {c.last_message_at ? formatShort(c.last_message_at, tenant.timezone) : "—"}
                    </p>
                  </div>
                  <Link href={`/dashboard/conversations?c=${c.id}`} className={buttonClass.link}>
                    Apri
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>Nessuna chat in attesa: l&apos;assistente gestisce tutto. 👌</EmptyState>
          )}
        </Card>
      </div>
    </div>
  );
}

async function loadServiceNames(tenantId: string, ids: (string | null)[] | undefined) {
  const unique = [...new Set((ids ?? []).filter((id): id is string => Boolean(id)))];
  if (!unique.length) return new Map<string, string>();
  const supabase = await createClient();
  const { data } = await supabase.from("services").select("id, name").eq("tenant_id", tenantId).in("id", unique);
  return new Map((data ?? []).map((s) => [s.id, s.name]));
}

function Stat({ label, value, suffix = "", tone = "slate" }: {
  label: string;
  value: number;
  suffix?: string;
  tone?: "slate" | "red";
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-semibold ${tone === "red" && value ? "text-rose-600" : ""}`}>
        {value}
        {suffix}
      </p>
      {tone === "red" && value ? <Badge tone="red">Richiede attenzione</Badge> : null}
    </div>
  );
}
