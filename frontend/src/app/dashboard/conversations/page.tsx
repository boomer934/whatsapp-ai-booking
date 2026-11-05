import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Badge, Card, EmptyState, PageHeader, Skeleton } from "@/components/ui";
import type { ConversationRow } from "@/lib/database.types";
import { getTenantContext } from "@/lib/dal";
import { STATE_LABELS, formatShort, formatTime } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";

import { ResumeAiButton } from "./resume-button";

export const metadata: Metadata = { title: "Conversazioni" };

type Search = PageProps<"/dashboard/conversations">["searchParams"];

export default function ConversationsPage({ searchParams }: PageProps<"/dashboard/conversations">) {
  return (
    <>
      <PageHeader
        title="Conversazioni"
        description="Le chat WhatsApp con i clienti. Quelle passate all'operatore aspettano una tua risposta."
      />
      <Suspense fallback={<Skeleton rows={6} />}>
        <Conversations searchParams={searchParams} />
      </Suspense>
    </>
  );
}

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

async function Conversations({ searchParams }: { searchParams: Search }) {
  const { tenant } = await getTenantContext();
  const params = await searchParams;
  const filter = one(params.filter) === "manual" ? "manual" : "all";
  const selectedId = one(params.c);
  const supabase = await createClient();

  let query = supabase
    .from("conversations")
    .select("*")
    .eq("tenant_id", tenant.id)
    .order("last_message_at", { ascending: false, nullsFirst: false })
    .limit(100);
  if (filter === "manual") query = query.eq("mode", "manual");
  const { data: conversations, error } = await query;
  if (error) throw new Error(error.message);

  const selected = conversations.find((c) => c.id === selectedId) ?? null;
  const href = (next: { filter?: string; c?: string }) => {
    const qs = new URLSearchParams();
    const f = next.filter ?? filter;
    if (f === "manual") qs.set("filter", "manual");
    if (next.c) qs.set("c", next.c);
    const s = qs.toString();
    return s ? `?${s}` : "?";
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <Card>
        <div className="mb-3 flex gap-2 text-sm">
          {(["all", "manual"] as const).map((f) => (
            <Link
              key={f}
              href={href({ filter: f, c: selected?.id })}
              className={`rounded-full px-3 py-1 ${filter === f ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-600"}`}
            >
              {f === "all" ? "Tutte" : "In attesa dell'operatore"}
            </Link>
          ))}
        </div>
        {conversations.length ? (
          <ul className="-mx-2 max-h-[65vh] overflow-y-auto">
            {conversations.map((c) => (
              <li key={c.id}>
                <Link
                  href={href({ c: c.id })}
                  className={`flex items-center justify-between gap-2 rounded-lg px-2 py-2.5 text-sm ${
                    c.id === selected?.id ? "bg-emerald-50" : "hover:bg-slate-50"
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{c.customer_name ?? c.customer_phone}</span>
                    <span className="block text-xs text-slate-500">{STATE_LABELS[c.state] ?? c.state}</span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1">
                    {c.mode === "manual" ? <Badge tone="red">Operatore</Badge> : null}
                    <span className="text-xs text-slate-400">
                      {c.last_message_at ? formatShort(c.last_message_at, tenant.timezone) : ""}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState>
            {filter === "manual" ? "Nessuna chat in attesa dell'operatore." : "Ancora nessuna conversazione."}
          </EmptyState>
        )}
      </Card>

      <Card>
        {selected ? (
          <ConversationDetail conversation={selected} timeZone={tenant.timezone} />
        ) : (
          <EmptyState>Seleziona una conversazione per leggere i messaggi.</EmptyState>
        )}
      </Card>
    </div>
  );
}

async function ConversationDetail({ conversation, timeZone }: { conversation: ConversationRow; timeZone: string }) {
  const supabase = await createClient();
  const { data: messages, error } = await supabase
    .from("messages")
    .select("id, direction, body, created_at")
    .eq("tenant_id", conversation.tenant_id)
    .eq("conversation_id", conversation.id)
    .order("created_at")
    .limit(300);
  if (error) throw new Error(error.message);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <p className="font-semibold">{conversation.customer_name ?? "Cliente"}</p>
          <a href={`tel:${conversation.customer_phone}`} className="text-sm text-slate-500 hover:underline">
            {conversation.customer_phone}
          </a>
          <div className="mt-2 flex gap-2">
            {conversation.mode === "manual" ? (
              <Badge tone="red">👤 Gestita dall&apos;operatore</Badge>
            ) : (
              <Badge tone="green">🤖 Gestita dall&apos;AI</Badge>
            )}
            <Badge>{STATE_LABELS[conversation.state] ?? conversation.state}</Badge>
          </div>
        </div>
        {conversation.mode === "manual" ? <ResumeAiButton conversationId={conversation.id} /> : null}
      </div>

      {conversation.mode === "manual" ? (
        <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          L&apos;assistente si è fermato e non risponde a questo cliente. Contattalo tu, poi premi
          «Riprendi AI» per riaffidargli la chat.
        </p>
      ) : null}

      <div className="max-h-[55vh] space-y-2 overflow-y-auto rounded-lg bg-[#efeae2] p-3">
        {messages.length ? (
          messages.map((m) => (
            <div
              key={m.id}
              className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm shadow-sm ${
                m.direction === "inbound" ? "bg-white" : "ml-auto bg-[#d9fdd3]"
              }`}
            >
              {m.body}
              <span className="mt-1 block text-right text-[11px] text-slate-500">
                {m.direction === "outbound" ? "Assistente · " : ""}
                {formatTime(m.created_at, timeZone)}
              </span>
            </div>
          ))
        ) : (
          <p className="text-center text-sm text-slate-500">Nessun messaggio.</p>
        )}
      </div>
    </div>
  );
}
