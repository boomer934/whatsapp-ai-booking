import type { Metadata } from "next";
import { Suspense } from "react";

import { Badge, Card, PageHeader, Skeleton } from "@/components/ui";
import { BackendError, backendFetch } from "@/lib/backend";
import { getTenantContext } from "@/lib/dal";

import { GoogleConnectButton, GoogleDisconnectButton, TenantForm } from "./settings-forms";

export const metadata: Metadata = { title: "Impostazioni" };

type Search = PageProps<"/dashboard/settings">["searchParams"];

const GOOGLE_ERRORS: Record<string, string> = {
  access_denied: "hai negato il consenso su Google.",
  missing_scopes: "non hai concesso entrambi i permessi (disponibilità ed eventi). Riprova selezionandoli tutti.",
  no_refresh_token: "Google non ha fornito un accesso permanente: rimuovi l'app dal tuo account Google e riprova.",
  invalid_state: "la richiesta è scaduta. Riprova.",
  forbidden: "non hai i permessi per questa attività.",
  exchange_failed: "Google ha rifiutato la richiesta. Riprova tra poco.",
  not_configured: "l'integrazione Google non è configurata sul server.",
};

export default function SettingsPage({ searchParams }: PageProps<"/dashboard/settings">) {
  return (
    <>
      <PageHeader title="Impostazioni" />
      <div className="space-y-6">
        <Suspense fallback={<Skeleton rows={1} />}>
          <GoogleResult searchParams={searchParams} />
        </Suspense>
        <Card title="La tua attività">
          <Suspense fallback={<Skeleton rows={3} />}>
            <TenantSettings />
          </Suspense>
        </Card>
        <Card title="Google Calendar">
          <Suspense fallback={<Skeleton rows={2} />}>
            <GoogleSettings />
          </Suspense>
        </Card>
        <Card title="Numero WhatsApp">
          <Suspense fallback={<Skeleton rows={1} />}>
            <WhatsAppSettings />
          </Suspense>
        </Card>
      </div>
    </>
  );
}

async function GoogleResult({ searchParams }: { searchParams: Search }) {
  const { google, reason } = await searchParams;
  if (google === "connected") {
    return <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">✅ Google Calendar collegato.</p>;
  }
  if (google === "error") {
    const key = typeof reason === "string" ? reason : "";
    return (
      <p role="alert" className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
        Collegamento non riuscito: {GOOGLE_ERRORS[key] ?? key ?? "errore sconosciuto."}
      </p>
    );
  }
  return null;
}

async function TenantSettings() {
  const { tenant } = await getTenantContext();
  return <TenantForm tenant={tenant} />;
}

type GoogleStatus = { connected: boolean; google_account_email: string | null; calendar_id: string | null };

async function GoogleSettings() {
  const { tenant } = await getTenantContext();
  let status: GoogleStatus | null = null;
  let problem: string | null = null;
  try {
    status = await backendFetch<GoogleStatus>(`/api/tenants/${tenant.id}/google`);
  } catch (error) {
    problem = error instanceof BackendError ? error.message : "Stato non disponibile.";
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Con il calendario collegato l&apos;assistente non propone orari in cui hai già impegni e
        aggiunge un evento per ogni prenotazione.
      </p>
      {problem ? (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{problem}</p>
      ) : status?.connected ? (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <Badge tone="green">Collegato</Badge>
            <span className="min-w-0 break-all">{status.google_account_email ?? "Account Google"}</span>
            <span className="min-w-0 break-all text-slate-400">· calendario {status.calendar_id}</span>
          </div>
          <GoogleDisconnectButton />
        </div>
      ) : (
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
          <Badge tone="amber">Non collegato</Badge>
          <GoogleConnectButton />
        </div>
      )}
    </div>
  );
}

async function WhatsAppSettings() {
  const { tenant } = await getTenantContext();
  const number = tenant.wa_phone_e164 ?? tenant.wa_phone_number_id;
  return number ? (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <Badge tone="green">Collegato</Badge>
      <span>{tenant.wa_phone_e164 ?? `ID ${tenant.wa_phone_number_id}`}</span>
      <span className="text-slate-400">({tenant.messaging_provider === "meta" ? "WhatsApp Cloud API" : "Twilio"})</span>
    </div>
  ) : (
    <p className="text-sm text-slate-600">
      Nessun numero collegato. Il collegamento del numero WhatsApp Business viene configurato dal
      supporto durante l&apos;attivazione del servizio.
    </p>
  );
}
