"use client";

import { useOptimistic, useState, useTransition } from "react";

import type { ActionState } from "@/lib/action-state";

import { setAiEnabled } from "./actions";

export function AiToggle({ enabled }: { enabled: boolean }) {
  const [optimistic, setOptimistic] = useOptimistic(enabled);
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<ActionState>(null);

  const toggle = () =>
    startTransition(async () => {
      setOptimistic(!optimistic);
      setResult(await setAiEnabled(!optimistic));
    });

  return (
    <div className="flex flex-wrap items-center gap-4">
      <button
        type="button"
        role="switch"
        aria-checked={optimistic}
        aria-label="Assistente AI"
        onClick={toggle}
        disabled={pending}
        className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors disabled:opacity-60 ${
          optimistic ? "bg-emerald-600" : "bg-slate-300"
        }`}
      >
        <span
          className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
            optimistic ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
      <div>
        <p className="font-medium">
          {optimistic ? "L'assistente risponde ai clienti" : "Assistente spento"}
        </p>
        <p className="text-sm text-slate-500">
          {optimistic
            ? "Interpreta le richieste e prenota in automatico su WhatsApp."
            : "I messaggi vengono salvati ma nessuno risponde in automatico."}
        </p>
      </div>
      {result?.error ? <p className="w-full text-sm text-rose-700">{result.error}</p> : null}
    </div>
  );
}
