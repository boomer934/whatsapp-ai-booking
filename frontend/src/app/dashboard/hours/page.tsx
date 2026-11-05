import type { Metadata } from "next";
import { Suspense } from "react";

import { Card, PageHeader, Skeleton } from "@/components/ui";
import { getTenantContext } from "@/lib/dal";
import { trimTime } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";

import { HoursEditor } from "./hours-editor";

export const metadata: Metadata = { title: "Orari" };

export default function HoursPage() {
  return (
    <>
      <PageHeader
        title="Orari di apertura"
        description="L'assistente propone solo orari dentro queste fasce. Aggiungi più fasce per la pausa pranzo."
      />
      <Card>
        <Suspense fallback={<Skeleton rows={7} />}>
          <Hours />
        </Suspense>
      </Card>
    </>
  );
}

async function Hours() {
  const { tenant } = await getTenantContext();
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("business_hours")
    .select("weekday, open_time, close_time")
    .eq("tenant_id", tenant.id);
  if (error) throw new Error(error.message);
  return (
    <HoursEditor
      initial={data.map((h) => ({
        weekday: h.weekday,
        open: trimTime(h.open_time),
        close: trimTime(h.close_time),
      }))}
    />
  );
}
