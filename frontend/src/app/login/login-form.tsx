"use client";

import { useSearchParams } from "next/navigation";

import { FormMessage, SubmitButton, useFormAction } from "@/components/form-controls";
import { Label, inputClass } from "@/components/ui";

import { signIn } from "./actions";

export function LoginForm() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const callbackError = searchParams.get("error");
  const [state, action] = useFormAction(signIn);

  return (
    <div>
      <p className="mb-6 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
        Servizio in fase di prova: l&apos;accesso è riservato alle attività autorizzate. Per
        richiederlo scrivi a{" "}
        <a className="font-medium underline" href="mailto:davide.webdeveloper934@gmail.com">
          davide.webdeveloper934@gmail.com
        </a>
        .
      </p>

      {callbackError ? (
        <p role="alert" className="mb-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          Il link non è valido o è scaduto. Accedi con email e password.
        </p>
      ) : null}

      <form action={action} className="space-y-4">
        <input type="hidden" name="next" value={next} />
        <div>
          <Label htmlFor="email">Email</Label>
          <input id="email" name="email" type="email" autoComplete="email" required defaultValue={state?.values?.email} className={inputClass} />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <input id="password" name="password" type="password" autoComplete="current-password" required className={inputClass} />
        </div>
        <FormMessage state={state} />
        <SubmitButton className="w-full" pendingText="Accesso…">
          Accedi
        </SubmitButton>
      </form>
    </div>
  );
}
