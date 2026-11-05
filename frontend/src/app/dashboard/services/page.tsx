import type { Metadata } from "next";
import { Suspense } from "react";

import { Card, EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { getTenantContext } from "@/lib/dal";
import { createClient } from "@/lib/supabase/server";

import { NewServiceForm, ServiceRowItem } from "./service-forms";

export const metadata: Metadata = { title: "Servizi" };

export default function ServicesPage() {
  return (
    <>
      <PageHeader
        title="Servizi"
        description="L'assistente propone ai clienti solo i servizi attivi, con la durata indicata."
      />
      <div className="space-y-6">
        <Card title="Nuovo servizio">
          <NewServiceForm />
        </Card>
        <Card title="I tuoi servizi">
          <Suspense fallback={<Skeleton rows={4} />}>
            <ServiceList />
          </Suspense>
        </Card>
      </div>
    </>
  );
}

async function ServiceList() {
  const { tenant } = await getTenantContext();
  const supabase = await createClient();
  const { data: services, error } = await supabase
    .from("services")
    .select("*")
    .eq("tenant_id", tenant.id)
    .order("name");
  if (error) throw new Error(error.message);
  if (!services.length) {
    return <EmptyState>Nessun servizio: aggiungine uno qui sopra per iniziare.</EmptyState>;
  }
  return (
    <ul className="divide-y divide-slate-100">
      {services.map((s) => (
        <ServiceRowItem key={s.id} service={s} />
      ))}
    </ul>
  );
}
