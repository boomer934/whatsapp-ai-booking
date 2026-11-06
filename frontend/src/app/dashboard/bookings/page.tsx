import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Badge, Card, EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { getTenantContext } from "@/lib/dal";
import { formatDay, formatTime } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";

import { CancelBookingButton } from "./cancel-button";

export const metadata: Metadata = { title: "Prenotazioni" };

const VIEWS = {
  upcoming: "Prossime",
  past: "Passate",
  cancelled: "Annullate",
} as const;
type View = keyof typeof VIEWS;

export default function BookingsPage({ searchParams }: PageProps<"/dashboard/bookings">) {
  return (
    <>
      <PageHeader
        title="Prenotazioni"
        description="Gli appuntamenti presi dall'assistente su WhatsApp."
      />
      <Suspense fallback={<Skeleton rows={6} />}>
        <Bookings searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function Bookings({ searchParams }: { searchParams: PageProps<"/dashboard/bookings">["searchParams"] }) {
  const { tenant } = await getTenantContext();
  const raw = (await searchParams).view;
  const view: View = typeof raw === "string" && raw in VIEWS ? (raw as View) : "upcoming";
  const supabase = await createClient();
  const nowIso = new Date().toISOString();

  let query = supabase
    .from("bookings")
    .select("id, starts_at, ends_at, status, customer_name, customer_phone, service_id, google_event_id")
    .eq("tenant_id", tenant.id)
    .limit(200);
  if (view === "upcoming") query = query.eq("status", "confirmed").gte("starts_at", nowIso).order("starts_at");
  if (view === "past") query = query.eq("status", "confirmed").lt("starts_at", nowIso).order("starts_at", { ascending: false });
  if (view === "cancelled") query = query.eq("status", "cancelled").order("starts_at", { ascending: false });

  const [{ data: bookings, error }, { data: services }] = await Promise.all([
    query,
    supabase.from("services").select("id, name").eq("tenant_id", tenant.id),
  ]);
  if (error) throw new Error(error.message);
  const serviceName = new Map((services ?? []).map((s) => [s.id, s.name]));

  // Raggruppa per giorno (nel fuso dell'attività).
  const groups = new Map<string, typeof bookings>();
  for (const b of bookings) {
    const day = formatDay(b.starts_at, tenant.timezone);
    groups.set(day, [...(groups.get(day) ?? []), b]);
  }

  return (
    <div className="space-y-4">
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 text-sm sm:mx-0 sm:px-0">
        {(Object.keys(VIEWS) as View[]).map((v) => (
          <Link
            key={v}
            href={v === "upcoming" ? "?" : `?view=${v}`}
            className={`shrink-0 rounded-full px-3 py-1.5 ${view === v ? "bg-emerald-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}
          >
            {VIEWS[v]}
          </Link>
        ))}
      </div>

      {bookings.length === 0 ? (
        <Card>
          <EmptyState>Nessuna prenotazione in questa sezione.</EmptyState>
        </Card>
      ) : (
        [...groups.entries()].map(([day, items]) => (
          <Card key={day} title={day}>
            <ul className="divide-y divide-slate-100">
              {items.map((b) => {
                const who = b.customer_name ?? b.customer_phone;
                return (
                  <li
                    key={b.id}
                    className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 gap-y-2 py-3 sm:flex sm:items-center sm:gap-4"
                  >
                    <div className="font-semibold tabular-nums sm:w-28 sm:shrink-0">
                      {formatTime(b.starts_at, tenant.timezone)}–{formatTime(b.ends_at, tenant.timezone)}
                    </div>
                    <div className="min-w-0 sm:flex-1">
                      <p className="font-medium">{serviceName.get(b.service_id ?? "") ?? "Servizio eliminato"}</p>
                      <p className="break-words text-sm text-slate-500">
                        {who}
                        {b.customer_name ? (
                          <>
                            {" · "}
                            <a href={`tel:${b.customer_phone}`} className="whitespace-nowrap hover:underline">
                              {b.customer_phone}
                            </a>
                          </>
                        ) : null}
                      </p>
                    </div>
                    <div className="col-span-2 flex flex-wrap items-center justify-end gap-3 empty:hidden sm:col-auto sm:flex-nowrap">
                      {b.google_event_id ? <Badge tone="green">📅 Google</Badge> : null}
                      {b.status === "cancelled" ? <Badge tone="red">Annullata</Badge> : null}
                      {view === "upcoming" ? <CancelBookingButton bookingId={b.id} label={who} /> : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>
        ))
      )}
    </div>
  );
}
