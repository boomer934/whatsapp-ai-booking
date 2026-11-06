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
            <li
              key={dayName}
              className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2 py-4 lg:flex lg:items-start lg:gap-3"
            >
              <div className="self-center font-medium lg:w-32 lg:shrink-0 lg:self-auto lg:pt-2">{dayName}</div>
              <div className="col-span-2 row-start-2 space-y-2 lg:flex-1">
                {ranges.length === 0 ? <p className="text-sm text-slate-400 lg:pt-2">Chiuso</p> : null}
                {ranges.map((r) => (
                  <div key={r.key} className="flex items-center gap-2">
                    <input
                      type="time"
                      value={r.open}
                      aria-label={`${dayName} apertura`}
                      onChange={(e) =>
                        update(day, (rs) => rs.map((x) => (x.key === r.key ? { ...x, open: e.target.value } : x)))
                      }
                      className={`${inputClass} min-w-0 flex-1 sm:max-w-32`}
                    />
                    <span className="text-slate-400">–</span>
                    <input
                      type="time"
                      value={r.close}
                      aria-label={`${dayName} chiusura`}
                      onChange={(e) =>
                        update(day, (rs) => rs.map((x) => (x.key === r.key ? { ...x, close: e.target.value } : x)))
                      }
                      className={`${inputClass} min-w-0 flex-1 sm:max-w-32`}
                    />
                    <button
                      type="button"
                      aria-label={`Rimuovi fascia ${dayName}`}
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600 sm:h-9 sm:w-9"
                      onClick={() => update(day, (rs) => rs.filter((x) => x.key !== r.key))}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex shrink-0 items-center gap-4 lg:gap-3 lg:pt-2">
                <button
                  type="button"
                  className={`${buttonClass.link} py-2 disabled:opacity-40 disabled:no-underline`}
                  disabled={ranges.length >= 4}
                  onClick={() => {
                    const last = ranges.at(-1);
                    update(day, (rs) => [...rs, last ? newRange(last.close, last.close < "19:00" ? "19:00" : "23:00") : newRange()]);
                  }}
                >
                  + Fascia
                </button>
                {ranges.length ? (
                  <button type="button" className={`${buttonClass.link} py-2 disabled:opacity-40 disabled:no-underline`} onClick={() => copyToAll(day)}>
                    Copia su tutti
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      {/* Su mobile il salvataggio resta a portata di pollice mentre si scorre la settimana. */}
      <div className="sticky bottom-0 -mx-4 space-y-3 border-t border-slate-200 bg-white/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none">
        <FormMessage state={state} />
        <SubmitButton className="w-full sm:w-auto">Salva orari</SubmitButton>
      </div>
    </form>
  );
}
