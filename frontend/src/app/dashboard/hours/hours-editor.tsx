"use client";

import { useActionState, useState } from "react";

import { FormMessage, SubmitButton } from "@/components/form-controls";
import { buttonClass, inputClass } from "@/components/ui";
import { WEEKDAYS } from "@/lib/format";

import { type HourRange, saveHours } from "./actions";

type Range = { key: number; open: string; close: string };
type Week = Range[][];

let nextKey = 1;
const newRange = (open = "09:00", close = "13:00"): Range => ({ key: nextKey++, open, close });

function toWeek(initial: HourRange[]): Week {
  const week: Week = Array.from({ length: 7 }, () => []);
  for (const r of [...initial].sort((a, b) => a.open.localeCompare(b.open))) {
    week[r.weekday].push(newRange(r.open, r.close));
  }
  return week;
}

export function HoursEditor({ initial }: { initial: HourRange[] }) {
  const [week, setWeek] = useState<Week>(() => toWeek(initial));
  const [state, action] = useActionState(saveHours, null);

  const update = (day: number, fn: (ranges: Range[]) => Range[]) =>
    setWeek((w) => w.map((ranges, d) => (d === day ? fn(ranges) : ranges)));

  const copyToAll = (from: number) =>
    setWeek((w) =>
      w.map((ranges, d) => (d === from ? ranges : w[from].map((r) => newRange(r.open, r.close)))),
    );

  const payload: HourRange[] = week.flatMap((ranges, weekday) =>
    ranges.map((r) => ({ weekday, open: r.open, close: r.close })),
  );

  return (
    <form action={action} className="space-y-4">
      <input type="hidden" name="ranges" value={JSON.stringify(payload)} />
      <ul className="divide-y divide-slate-100">
        {WEEKDAYS.map((dayName, day) => {
          const ranges = week[day];
          return (
            <li key={dayName} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start">
              <div className="w-32 shrink-0 pt-2 font-medium">{dayName}</div>
              <div className="flex-1 space-y-2">
                {ranges.length === 0 ? <p className="pt-2 text-sm text-slate-400">Chiuso</p> : null}
                {ranges.map((r) => (
                  <div key={r.key} className="flex items-center gap-2">
                    <input
                      type="time"
                      value={r.open}
                      aria-label={`${dayName} apertura`}
                      onChange={(e) =>
                        update(day, (rs) => rs.map((x) => (x.key === r.key ? { ...x, open: e.target.value } : x)))
                      }
                      className={`${inputClass} max-w-32`}
                    />
                    <span className="text-slate-400">–</span>
                    <input
                      type="time"
                      value={r.close}
                      aria-label={`${dayName} chiusura`}
                      onChange={(e) =>
                        update(day, (rs) => rs.map((x) => (x.key === r.key ? { ...x, close: e.target.value } : x)))
                      }
                      className={`${inputClass} max-w-32`}
                    />
                    <button
                      type="button"
                      aria-label={`Rimuovi fascia ${dayName}`}
                      className="rounded-lg px-2 py-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                      onClick={() => update(day, (rs) => rs.filter((x) => x.key !== r.key))}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex shrink-0 gap-3 sm:pt-2">
                <button
                  type="button"
                  className={buttonClass.link}
                  disabled={ranges.length >= 4}
                  onClick={() => {
                    const last = ranges.at(-1);
                    update(day, (rs) => [...rs, last ? newRange(last.close, last.close < "19:00" ? "19:00" : "23:00") : newRange()]);
                  }}
                >
                  + Fascia
                </button>
                {ranges.length ? (
                  <button type="button" className={buttonClass.link} onClick={() => copyToAll(day)}>
                    Copia su tutti
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      <FormMessage state={state} />
      <SubmitButton>Salva orari</SubmitButton>
    </form>
  );
}
