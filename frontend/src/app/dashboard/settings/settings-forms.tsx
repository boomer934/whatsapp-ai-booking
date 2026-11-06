"use client";

import { useActionState } from "react";

import { FormMessage, SubmitButton, useFormAction } from "@/components/form-controls";
import { Label, inputClass } from "@/components/ui";
import type { TenantRow } from "@/lib/database.types";
import { TIMEZONES } from "@/lib/timezones";

import { connectGoogle, disconnectGoogle, updateTenant } from "./actions";

export function TenantForm({ tenant }: { tenant: TenantRow }) {
  const [state, action] = useFormAction(updateTenant);
  const knownTimezone = TIMEZONES.some((tz) => tz.value === tenant.timezone);
  return (
    <form action={action} className="space-y-4">
      <div>
        <Label htmlFor="name">Nome dell&apos;attività</Label>
        <input id="name" name="name" required maxLength={120} defaultValue={state?.values?.name ?? tenant.name} className={inputClass} />
      </div>
      <div>
        <Label htmlFor="timezone">Fuso orario</Label>
        <select id="timezone" name="timezone" defaultValue={state?.values?.timezone ?? tenant.timezone} className={inputClass}>
          {!knownTimezone ? <option value={tenant.timezone}>{tenant.timezone}</option> : null}
          {TIMEZONES.map((tz) => (
            <option key={tz.value} value={tz.value}>
              {tz.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label htmlFor="operator_phone" hint="(riceve gli avvisi quando una chat passa a te)">
          WhatsApp dell&apos;operatore
        </Label>
        <input
          id="operator_phone"
          name="operator_phone"
          type="tel"
          placeholder="+39 333 1234567"
          defaultValue={state?.values?.operator_phone ?? tenant.operator_phone ?? ""}
          className={inputClass}
        />
      </div>
      <FormMessage state={state} />
      <SubmitButton className="w-full sm:w-auto">Salva</SubmitButton>
    </form>
  );
}

export function GoogleConnectButton() {
  const [state, action] = useActionState(connectGoogle, null);
  return (
    <form action={action} className="w-full space-y-2 sm:w-auto">
      <SubmitButton className="w-full sm:w-auto" pendingText="Apertura di Google…">Collega Google Calendar</SubmitButton>
      <FormMessage state={state} />
    </form>
  );
}

export function GoogleDisconnectButton() {
  const [state, action] = useActionState(disconnectGoogle, null);
  return (
    <form
      action={action}
      className="w-full space-y-2 sm:w-auto"
      onSubmit={(e) => {
        if (!confirm("Scollegare Google Calendar? L'assistente non vedrà più i tuoi impegni.")) e.preventDefault();
      }}
    >
      <SubmitButton variant="danger" className="w-full sm:w-auto" pendingText="Scollegamento…">
        Scollega
      </SubmitButton>
      <FormMessage state={state} />
    </form>
  );
}
