/**
 * Tipi del database Supabase, allineati a supabase/migrations/0001 e 0002.
 * Aggiornare insieme alle migrazioni.
 */

export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type ConversationState =
  | "idle"
  | "selecting_service"
  | "selecting_slot"
  | "confirming"
  | "completed";
export type ConversationMode = "ai" | "manual";
export type MessageDirection = "inbound" | "outbound";
export type BookingStatus = "confirmed" | "cancelled";
export type MemberRole = "owner" | "staff";
export type MessagingProvider = "meta" | "twilio";

type Table<Row, Insert, Update = Partial<Insert>> = {
  Row: Row;
  Insert: Insert;
  Update: Update;
  Relationships: [];
};

export type TenantRow = {
  id: string;
  name: string;
  timezone: string;
  ai_enabled: boolean;
  messaging_provider: MessagingProvider;
  wa_phone_number_id: string | null;
  wa_phone_e164: string | null;
  operator_phone: string | null;
  created_at: string;
  updated_at: string;
};

export type ServiceRow = {
  id: string;
  tenant_id: string;
  name: string;
  duration_minutes: number;
  price_cents: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BusinessHoursRow = {
  id: string;
  tenant_id: string;
  weekday: number;
  open_time: string;
  close_time: string;
  created_at: string;
};

export type ConversationRow = {
  id: string;
  tenant_id: string;
  customer_phone: string;
  customer_name: string | null;
  state: ConversationState;
  mode: ConversationMode;
  failed_attempts: number;
  context: Json;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MessageRow = {
  id: string;
  tenant_id: string;
  conversation_id: string;
  direction: MessageDirection;
  body: string;
  provider_message_id: string | null;
  created_at: string;
};

export type BookingRow = {
  id: string;
  tenant_id: string;
  conversation_id: string | null;
  service_id: string | null;
  customer_phone: string;
  customer_name: string | null;
  starts_at: string;
  ends_at: string;
  status: BookingStatus;
  google_event_id: string | null;
  created_at: string;
  updated_at: string;
};

export type TenantMemberRow = {
  id: string;
  tenant_id: string;
  user_id: string;
  role: MemberRole;
  created_at: string;
};

export type Database = {
  public: {
    Tables: {
      tenants: Table<
        TenantRow,
        Pick<TenantRow, "name"> & Partial<TenantRow>,
        Partial<Pick<TenantRow, "name" | "timezone" | "ai_enabled" | "operator_phone">>
      >;
      tenant_members: Table<TenantMemberRow, Pick<TenantMemberRow, "tenant_id" | "user_id">>;
      services: Table<
        ServiceRow,
        Pick<ServiceRow, "tenant_id" | "name" | "duration_minutes"> & Partial<ServiceRow>
      >;
      business_hours: Table<
        BusinessHoursRow,
        Pick<BusinessHoursRow, "tenant_id" | "weekday" | "open_time" | "close_time">
      >;
      conversations: Table<
        ConversationRow,
        Pick<ConversationRow, "tenant_id" | "customer_phone">,
        Partial<Pick<ConversationRow, "mode" | "failed_attempts">>
      >;
      messages: Table<MessageRow, never, never>;
      bookings: Table<BookingRow, never, Partial<Pick<BookingRow, "status">>>;
    };
    Views: { [_ in never]: never };
    Functions: {
      create_tenant: { Args: { p_name: string; p_timezone?: string }; Returns: string };
      is_tenant_member: { Args: { p_tenant_id: string }; Returns: boolean };
    };
    Enums: {
      conversation_state: ConversationState;
      conversation_mode: ConversationMode;
      message_direction: MessageDirection;
      booking_status: BookingStatus;
      member_role: MemberRole;
      messaging_provider: MessagingProvider;
    };
    CompositeTypes: { [_ in never]: never };
  };
};
