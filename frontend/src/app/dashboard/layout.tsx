import { Suspense } from "react";

import { getTenantContext } from "@/lib/dal";

import { signOut } from "../login/actions";
import { MobileNav } from "./mobile-nav";
import { NavLinks } from "./nav-links";

/** Guscio statico della dashboard; i dati dell'account arrivano in streaming. */
export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  const account = (
    <Suspense fallback={<div className="h-16 animate-pulse rounded-lg bg-slate-100" />}>
      <AccountBox />
    </Suspense>
  );

  return (
    <div className="min-h-dvh md:flex">
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-700 text-lg text-white">
            💬
          </span>
          <span className="font-semibold">Assistente WhatsApp</span>
        </div>
        <NavLinks />
        <div className="mt-auto border-t border-slate-200 pt-4">{account}</div>
      </aside>

      <MobileNav account={account} />

      <main className="min-w-0 flex-1 px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-5 sm:px-6 md:px-10 md:py-8">
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
        <button className="-ml-2 min-h-11 rounded-lg px-2 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-900 md:min-h-0 md:py-1">
          Esci →
        </button>
      </form>
    </div>
  );
}
