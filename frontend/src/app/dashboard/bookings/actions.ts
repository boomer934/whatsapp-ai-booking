"use server";

import { refresh } from "next/cache";

import { type ActionState, fail, ok } from "@/lib/action-state";
import { BackendError, backendFetch } from "@/lib/backend";
import { getTenantContext } from "@/lib/dal";

type CancelResponse = { status: string; google_event_removed: boolean };

/** Annulla tramite backend: libera lo slot e rimuove l'evento da Google Calendar. */
export async function cancelBooking(bookingId: string): Promise<ActionState> {
  const { tenant } = await getTenantContext();
  try {
    const result = await backendFetch<CancelResponse>(
      `/api/tenants/${tenant.id}/bookings/${encodeURIComponent(bookingId)}/cancel`,
      { method: "POST" },
    );
    refresh();
    return ok(
      result?.google_event_removed
        ? "Prenotazione annullata e rimossa da Google Calendar."
        : "Prenotazione annullata.",
    );
  } catch (error) {
    return fail(error instanceof BackendError ? error.message : "Annullamento non riuscito.");
  }
}
