"use client";

import { FormMessage, SubmitButton, useFormAction } from "@/components/form-controls";
import { Label, inputClass } from "@/components/ui";
import { TIMEZONES } from "@/lib/timezones";

import { createTenant } from "./actions";

export function OnboardingForm() {
  const [state, action] = useFormAction(createTenant);
  return (
    <form action={action} className="space-y-4">
      <div>
        <Label htmlFor="name">Nome dell&apos;attività</Label>
        <input
          id="name"
          name="name"
          required
          maxLength={120}
          defaultValue={state?.values?.name}
          placeholder="Es. Salone Bella Vita"
          className={inputClass}
        />
        <p className="mt-1 text-xs text-slate-500">È il nome che l&apos;assistente usa con i clienti.</p>
      </div>
      <div>
        <Label htmlFor="timezone">Fuso orario</Label>
        <select id="timezone" name="timezone" defaultValue={state?.values?.timezone ?? "Europe/Rome"} className={inputClass}>
          {TIMEZONES.map((tz) => (
            <option key={tz.value} value={tz.value}>
              {tz.label}
            </option>
          ))}
        </select>
      </div>
      <FormMessage state={state} />
      <SubmitButton className="w-full" pendingText="Creazione…">
        Crea la mia attività
      </SubmitButton>
    </form>
  );
}
