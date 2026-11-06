"use client";

import { useState, useTransition } from "react";

import { FormMessage, SubmitButton, useFormAction } from "@/components/form-controls";
import { Badge, buttonClass, inputClass } from "@/components/ui";
import type { ActionState } from "@/lib/action-state";
import type { ServiceRow } from "@/lib/database.types";
import { formatPrice } from "@/lib/format";

import { createService, deleteService, setServiceActive, updateService } from "./actions";

function priceToInput(cents: number | null): string {
  return cents === null ? "" : (cents / 100).toFixed(2).replace(".", ",").replace(",00", "");
}

function ServiceFields({ service, values }: { service?: ServiceRow; values?: Record<string, string> }) {
  return (
    <>
      <input
        name="name"
        required
        maxLength={120}
        defaultValue={values?.name ?? service?.name}
        placeholder="Nome (es. Taglio donna)"
        aria-label="Nome del servizio"
        className={`${inputClass} sm:flex-[2]`}
      />
      <div className="grid grid-cols-2 gap-3 sm:contents">
      <div className="flex min-w-0 items-center gap-1 sm:flex-1">
        <input
          name="duration_minutes"
          type="number"
          min={5}
          max={600}
          step={5}
          required
          defaultValue={values?.duration_minutes ?? service?.duration_minutes ?? 30}
          aria-label="Durata in minuti"
          className={inputClass}
        />
        <span className="text-sm text-slate-500">min</span>
      </div>
      <div className="flex min-w-0 items-center gap-1 sm:flex-1">
        <input
          name="price"
          inputMode="decimal"
          defaultValue={values?.price ?? priceToInput(service?.price_cents ?? null)}
          placeholder="Prezzo"
          aria-label="Prezzo in euro"
          className={inputClass}
        />
        <span className="text-sm text-slate-500">€</span>
      </div>
      </div>
    </>
  );
}

export function NewServiceForm() {
  const [state, action] = useFormAction(createService);
  return (
    <form action={action} className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row">
        <ServiceFields key={state?.success ?? "new"} values={state?.values} />
        <SubmitButton pendingText="Aggiunta…" className="w-full sm:w-auto">
          Aggiungi
        </SubmitButton>
      </div>
      <FormMessage state={state} />
    </form>
  );
}

export function ServiceRowItem({ service }: { service: ServiceRow }) {
  const [editing, setEditing] = useState(false);
  const [state, action] = useFormAction(async (prev: ActionState, fd: FormData) => {
    const result = await updateService(prev, fd);
    if (result?.success) setEditing(false);
    return result;
  });
  const [pending, startTransition] = useTransition();
  const [rowResult, setRowResult] = useState<ActionState>(null);

  const run = (fn: () => Promise<ActionState>) =>
    startTransition(async () => setRowResult(await fn()));

  if (editing) {
    return (
      <li className="py-3">
        <form action={action} className="space-y-2">
          <input type="hidden" name="id" value={service.id} />
          <div className="flex flex-col gap-3 sm:flex-row">
            <ServiceFields service={service} values={state?.values} />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <SubmitButton>Salva</SubmitButton>
            <button type="button" className={buttonClass.secondary} onClick={() => setEditing(false)}>
              Annulla
            </button>
          </div>
          <FormMessage state={state} />
        </form>
      </li>
    );
  }

  return (
    <li className={`flex flex-wrap items-center gap-3 py-3 ${pending ? "opacity-60" : ""}`}>
      <div className="min-w-0 flex-1">
        <p className="break-words font-medium">
          {service.name}{" "}
          {!service.is_active ? <Badge tone="amber">Non prenotabile</Badge> : null}
        </p>
        <p className="text-sm text-slate-500">
          {service.duration_minutes} min · {formatPrice(service.price_cents)}
        </p>
        {rowResult?.error ? <p className="text-sm text-rose-700">{rowResult.error}</p> : null}
      </div>
      <div className="grid w-full grid-cols-3 gap-2 sm:flex sm:w-auto max-sm:[&>button]:px-2">
        <button type="button" className={buttonClass.secondary} onClick={() => setEditing(true)}>
          Modifica
        </button>
        <button
          type="button"
          className={buttonClass.secondary}
          disabled={pending}
          onClick={() => run(() => setServiceActive(service.id, !service.is_active))}
        >
          {service.is_active ? "Disattiva" : "Attiva"}
        </button>
        <button
          type="button"
          className={buttonClass.danger}
          disabled={pending}
          onClick={() => {
            if (confirm(`Eliminare "${service.name}"? Le prenotazioni esistenti restano.`)) {
              run(() => deleteService(service.id));
            }
          }}
        >
          Elimina
        </button>
      </div>
    </li>
  );
}
