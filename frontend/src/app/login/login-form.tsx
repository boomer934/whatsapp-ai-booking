"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { FormMessage, SubmitButton, useFormAction } from "@/components/form-controls";
import { Label, inputClass } from "@/components/ui";

import { signIn, signUp } from "./actions";

type Mode = "login" | "signup";

export function LoginForm() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const callbackError = searchParams.get("error");
  const [mode, setMode] = useState<Mode>("login");
  const [loginState, loginAction] = useFormAction(signIn);
  const [signupState, signupAction] = useFormAction(signUp);
  const isLogin = mode === "login";
  const state = isLogin ? loginState : signupState;

  return (
    <div>
      <div className="mb-6 grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm font-medium">
        {(["login", "signup"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded-md py-2 ${mode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
          >
            {m === "login" ? "Accedi" : "Registrati"}
          </button>
        ))}
      </div>

      {callbackError ? (
        <p role="alert" className="mb-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          Il link di conferma non è valido o è scaduto. Accedi o registrati di nuovo.
        </p>
      ) : null}

      <form action={isLogin ? loginAction : signupAction} className="space-y-4" key={mode}>
        <input type="hidden" name="next" value={next} />
        <div>
          <Label htmlFor="email">Email</Label>
          <input id="email" name="email" type="email" autoComplete="email" required defaultValue={state?.values?.email} className={inputClass} />
        </div>
        <div>
          <Label htmlFor="password" hint={isLogin ? undefined : "(almeno 8 caratteri)"}>
            Password
          </Label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            minLength={isLogin ? undefined : 8}
            required
            className={inputClass}
          />
        </div>
        <FormMessage state={state} />
        <SubmitButton className="w-full" pendingText={isLogin ? "Accesso…" : "Registrazione…"}>
          {isLogin ? "Accedi" : "Crea account"}
        </SubmitButton>
      </form>
    </div>
  );
}
