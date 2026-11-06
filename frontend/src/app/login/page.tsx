import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Accedi" };

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-700 text-2xl text-white">
            💬
          </div>
          <h1 className="text-xl font-semibold">Assistente WhatsApp</h1>
          <p className="mt-1 text-sm text-slate-500">Prenotazioni automatiche per la tua attività</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          {/* useSearchParams richiede un confine Suspense durante il prerendering. */}
          <Suspense fallback={<Skeleton rows={4} />}>
            <LoginForm />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
