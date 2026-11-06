"use client";

import { useEffect } from "react";

import { buttonClass } from "@/components/ui";

export default function DashboardError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="rounded-xl border border-rose-200 bg-white p-6 text-center sm:p-8 shadow-sm">
      <p className="text-3xl">⚠️</p>
      <h2 className="mt-2 text-lg font-semibold">Qualcosa non ha funzionato</h2>
      <p className="mt-1 text-sm text-slate-500">
        Non siamo riusciti a caricare questa pagina. Controlla la connessione e riprova.
      </p>
      <button type="button" onClick={() => retry()} className={`mt-4 ${buttonClass.primary}`}>
        Riprova
      </button>
    </div>
  );
}
