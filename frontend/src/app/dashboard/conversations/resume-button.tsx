"use client";

import { useState, useTransition } from "react";

import { buttonClass } from "@/components/ui";
import type { ActionState } from "@/lib/action-state";

import { resumeAi } from "../actions";

export function ResumeAiButton({ conversationId }: { conversationId: string }) {
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<ActionState>(null);
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        className={buttonClass.primary}
        disabled={pending}
        onClick={() => startTransition(async () => setResult(await resumeAi(conversationId)))}
      >
        {pending ? "Attendere…" : "🤖 Riprendi AI"}
      </button>
      {result?.error ? <p className="text-sm text-rose-700">{result.error}</p> : null}
    </div>
  );
}
