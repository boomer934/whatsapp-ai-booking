"use client";

import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { LINKS, NavLinks, isActiveLink } from "./nav-links";

/**
 * Barra superiore e menu a scomparsa per gli schermi piccoli (sotto `md`).
 * `account` è un Server Component già renderizzato (nome attività, email, "Esci").
 */
export function MobileNav({ account }: { account: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const current = LINKS.find((link) => isActiveLink(pathname, link.href));

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 pt-[env(safe-area-inset-top)] backdrop-blur md:hidden">
        <div className="flex h-14 items-center gap-3 px-2">
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Apri il menu"
            aria-expanded={open}
            aria-controls="mobile-menu"
            className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100"
          >
            <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <span className="flex min-w-0 items-center gap-2 font-semibold">
            <span aria-hidden>{current?.icon ?? "💬"}</span>
            <span className="truncate">{current?.label ?? "Assistente WhatsApp"}</span>
          </span>
        </div>
      </header>

      <div
        className={`fixed inset-0 z-40 md:hidden ${open ? "" : "pointer-events-none"}`}
        aria-hidden={!open}
      >
        <div
          onClick={() => setOpen(false)}
          className={`absolute inset-0 bg-slate-900/40 transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0"}`}
        />
        <div
          id="mobile-menu"
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
          inert={!open}
          className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-white px-3 pb-[max(1rem,env(safe-area-inset-bottom))] pt-[max(0.75rem,env(safe-area-inset-top))] shadow-xl transition-transform duration-200 ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-4 flex items-center justify-between pl-2">
            <span className="flex items-center gap-2 font-semibold">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-700 text-lg text-white">
                💬
              </span>
              Assistente WhatsApp
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Chiudi il menu"
              className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
            >
              <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <NavLinks onNavigate={() => setOpen(false)} />
          </div>
          <div className="border-t border-slate-200 pt-4">{account}</div>
        </div>
      </div>
    </>
  );
}
