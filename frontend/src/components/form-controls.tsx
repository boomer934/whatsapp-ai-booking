"use client";

import { type ReactNode, useActionState } from "react";
import { useFormStatus } from "react-dom";

import { buttonClass } from "@/components/ui";
import type { ActionState } from "@/lib/action-state";

/** Pulsante di invio che si disattiva mentre la Server Action è in corso. */
export function SubmitButton({
  children,
  pendingText = "Salvataggio…",
  variant = "primary",
  className = "",
}: {
  children: ReactNode;
  pendingText?: string;
  variant?: keyof typeof buttonClass;
  className?: string;
}) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} className={`${buttonClass[variant]} ${className}`}>
      {pending ? pendingText : children}
    </button>
  );
}

export function FormMessage({ state }: { state: ActionState }) {
  if (!state) return null;
  if (state.error) {
    return (
      <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
        {state.error}
      </p>
    );
  }
  if (state.success) {
    return (
      <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
        {state.success}
      </p>
    );
  }
  return null;
}

type FormAction = (prev: ActionState, formData: FormData) => Promise<ActionState>;

/**
 * useActionState che, in caso di errore, conserva quanto scritto dall'utente:
 * React 19 azzera i campi non controllati dopo ogni invio, quindi i form usano
 * `defaultValue={state?.values?.campo ?? valoreSalvato}`. Le password non vengono mai conservate.
 */
export function useFormAction(action: FormAction) {
  return useActionState(async (prev: ActionState, formData: FormData): Promise<ActionState> => {
    const result = await action(prev, formData);
    if (!result?.error) return result;
    const values: Record<string, string> = {};
    formData.forEach((value, key) => {
      if (typeof value === "string" && key !== "password" && !key.startsWith("$")) values[key] = value;
    });
    return { ...result, values };
  }, null);
}
