"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/dashboard", label: "Panoramica", icon: "🏠" },
  { href: "/dashboard/bookings", label: "Prenotazioni", icon: "📅" },
  { href: "/dashboard/conversations", label: "Conversazioni", icon: "💬" },
  { href: "/dashboard/services", label: "Servizi", icon: "✂️" },
  { href: "/dashboard/hours", label: "Orari", icon: "🕘" },
  { href: "/dashboard/settings", label: "Impostazioni", icon: "⚙️" },
] as const;

export function NavLinks({ orientation = "vertical" }: { orientation?: "vertical" | "horizontal" }) {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === href : pathname.startsWith(href);

  return (
    <nav
      className={
        orientation === "vertical" ? "flex flex-col gap-1" : "flex gap-1 overflow-x-auto pb-1"
      }
    >
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          aria-current={isActive(link.href) ? "page" : undefined}
          className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
            isActive(link.href)
              ? "bg-emerald-50 text-emerald-800"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          }`}
        >
          <span aria-hidden>{link.icon}</span>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
