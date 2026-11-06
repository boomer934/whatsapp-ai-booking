"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const LINKS = [
  { href: "/dashboard", label: "Panoramica", icon: "🏠" },
  { href: "/dashboard/bookings", label: "Prenotazioni", icon: "📅" },
  { href: "/dashboard/conversations", label: "Conversazioni", icon: "💬" },
  { href: "/dashboard/services", label: "Servizi", icon: "✂️" },
  { href: "/dashboard/hours", label: "Orari", icon: "🕘" },
  { href: "/dashboard/settings", label: "Impostazioni", icon: "⚙️" },
] as const;

export function isActiveLink(pathname: string, href: string): boolean {
  return href === "/dashboard" ? pathname === href : pathname.startsWith(href);
}

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1">
      {LINKS.map((link) => {
        const active = isActiveLink(pathname, link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-base font-medium md:gap-2 md:py-2 md:text-sm ${
              active
                ? "bg-emerald-50 text-emerald-800"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            <span aria-hidden>{link.icon}</span>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
