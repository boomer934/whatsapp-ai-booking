import type { ReactNode } from "react";

/** Componenti di presentazione condivisi (Server Components). */

export function PageHeader({ title, description, action }: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 sm:mb-6 sm:gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">{title}</h1>
        {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Card({ title, children, className = "" }: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5 ${className}`}>
      {title ? (
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          {title}
        </h2>
      ) : null}
      {children}
    </section>
  );
}

const BADGE_TONES = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  red: "bg-rose-50 text-rose-700 ring-rose-600/20",
  amber: "bg-amber-50 text-amber-800 ring-amber-600/20",
  slate: "bg-slate-100 text-slate-700 ring-slate-500/20",
} as const;

export function Badge({ tone = "slate", children }: {
  tone?: keyof typeof BADGE_TONES;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
      {children}
    </p>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-3" aria-label="Caricamento">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-12 rounded-lg bg-slate-200/70" />
      ))}
    </div>
  );
}

export const inputClass =
  "block w-full rounded-lg border border-slate-300 bg-white min-h-11 px-3 py-2 text-base text-slate-900 shadow-sm sm:min-h-0 sm:text-sm placeholder:text-slate-400 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/20 disabled:bg-slate-50";

export const buttonClass = {
  primary:
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-0",
  secondary:
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-0",
  danger:
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-0",
  link: "text-sm font-medium text-emerald-700 hover:text-emerald-800 hover:underline",
} as const;

export function Label({ htmlFor, children, hint }: {
  htmlFor: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-slate-700">
      {children}
      {hint ? <span className="ml-1 font-normal text-slate-400">{hint}</span> : null}
    </label>
  );
}
