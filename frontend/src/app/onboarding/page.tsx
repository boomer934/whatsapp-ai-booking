import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui";
import { getCurrentUser } from "@/lib/dal";
import { createClient } from "@/lib/supabase/server";

import { OnboardingForm } from "./onboarding-form";

export const metadata: Metadata = { title: "Configura la tua attività" };

export default function OnboardingPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold">Benvenuto! 👋</h1>
        <p className="mb-6 mt-1 text-sm text-slate-500">
          Crea la tua attività: poi aggiungerai servizi e orari e l&apos;assistente sarà pronto a
          prenotare su WhatsApp.
        </p>
        <Suspense fallback={<Skeleton rows={3} />}>
          <OnboardingGate />
        </Suspense>
      </div>
    </main>
  );
}

/** Chi ha già un'attività non deve crearne un'altra. */
async function OnboardingGate() {
  const user = await getCurrentUser();
  const supabase = await createClient();
  const { count } = await supabase
    .from("tenant_members")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id);
  if (count) redirect("/dashboard");
  return <OnboardingForm />;
}
