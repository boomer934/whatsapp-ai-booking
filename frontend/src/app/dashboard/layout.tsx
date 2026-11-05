import { Suspense } from "react";

import { getTenantContext } from "@/lib/dal";

import { signOut } from "../login/actions";
import { NavLinks } from "./nav-links";

/** Guscio statico della dashboard; i dati dell'account arrivano in streaming. */
export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-700 text-lg text-white">
            💬
          </span>
          <span className="font-semibold">Assistente WhatsApp</span>
        </div>
        <NavLinks />
        <div className="mt-auto border-t border-slate-200 pt-4">
          <Suspense fallback={<div className="h-16 animate-pulse rounded-lg bg-slate-100" />}>
            <AccountBox />
          </Suspense>
        </div>
      </aside>

      <header className="border-b border-slate-200 bg-white px-4 pt-3 md:hidden">
        <div className="mb-2 flex items-center justify-between">
          <span className="font-semibold">💬 Assistente WhatsApp</span>
          <form action={signOut}>
            <button className="text-sm text-slate-500">Esci</button>
          </form>
        </div>
        <NavLinks orientation="horizontal" />
      </header>

      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}

async function AccountBox() {
  const { tenant, user } = await getTenantContext();
  return (
    <div className="px-2">
      <p className="truncate text-sm font-medium text-slate-900">{tenant.name}</p>
      <p className="truncate text-xs text-slate-500">{user.email}</p>
      <form action={signOut} className="mt-2">
        <button className="text-sm text-slate-500 hover:text-slate-900">Esci →</button>
      </form>
    </div>
  );
}
