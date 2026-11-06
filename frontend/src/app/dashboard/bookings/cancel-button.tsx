"use client";

import { useState, useTransition } from "react";

import { buttonClass } from "@/components/ui";
import type { ActionState } from "@/lib/action-state";

import { cancelBooking } from "./actions";

export function CancelBookingButton({ bookingId, label }: { bookingId: string; label: string }) {
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<ActionState>(null);
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        className={buttonClass.danger}
        disabled={pending}
        onClick={() => {
          if (confirm(`Annullare la prenotazione di ${label}? Il cliente non viene avvisato in automatico.`)) {
            startTransition(async () => setResult(await cancelBooking(bookingId)));
          }
        }}
      >
        {pending ? "Annullamento…" : "Annulla"}
      </button>
      {result?.error ? <p className="max-w-full text-right sm:max-w-56 text-xs text-rose-700">{result.error}</p> : null}
    </div>
  );
}
