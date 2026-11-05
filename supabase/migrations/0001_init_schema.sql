-- =============================================================================
-- 0001_init_schema.sql
-- Schema iniziale multi-tenant per WhatsApp AI Booking.
--
-- Regole:
--   * Tutte le PK sono UUID (gen_random_uuid()).
--   * Ogni tabella di dominio ha `tenant_id`.
--   * Le FK tra tabelle figlie usano la coppia (id, tenant_id): il DB garantisce
--     che un record non possa mai riferirsi a dati di un altro tenant.
--   * Requisito: PostgreSQL 15+ (default su Supabase) per ON DELETE SET NULL (col).
-- =============================================================================

create extension if not exists btree_gist;

-- -----------------------------------------------------------------------------
-- Tipi enum (allineati a backend/app/models/enums.py)
-- -----------------------------------------------------------------------------
create type public.conversation_state as enum (
    'idle', 'selecting_service', 'selecting_slot', 'confirming', 'completed'
);
create type public.conversation_mode as enum ('ai', 'manual');
create type public.message_direction as enum ('inbound', 'outbound');
create type public.booking_status as enum ('confirmed', 'cancelled');
create type public.member_role as enum ('owner', 'staff');
create type public.messaging_provider as enum ('meta', 'twilio');

-- -----------------------------------------------------------------------------
-- Trigger generico per updated_at
-- -----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- -----------------------------------------------------------------------------
-- tenants: una riga per attività cliente
-- -----------------------------------------------------------------------------
create table public.tenants (
    id                  uuid primary key default gen_random_uuid(),
    name                text not null check (char_length(name) between 1 and 120),
    timezone            text not null default 'Europe/Rome',
    ai_enabled          boolean not null default true,
    messaging_provider  public.messaging_provider not null default 'meta',
    -- Routing webhook Meta: phone_number_id del numero WhatsApp Business.
    wa_phone_number_id  text unique,
    -- Routing webhook Twilio: numero destinatario in formato E.164 (es. +14155238886).
    wa_phone_e164       text unique,
    -- Numero WhatsApp dell'operatore da avvisare in caso di handover.
    operator_phone      text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create trigger tenants_set_updated_at
    before update on public.tenants
    for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- tenant_members: utenti Supabase Auth che gestiscono un tenant
-- -----------------------------------------------------------------------------
create table public.tenant_members (
    id          uuid primary key default gen_random_uuid(),
    tenant_id   uuid not null references public.tenants (id) on delete cascade,
    user_id     uuid not null references auth.users (id) on delete cascade,
    role        public.member_role not null default 'owner',
    created_at  timestamptz not null default now(),
    unique (tenant_id, user_id)
);

create index tenant_members_user_id_idx on public.tenant_members (user_id);

-- -----------------------------------------------------------------------------
-- services: catalogo servizi prenotabili
-- -----------------------------------------------------------------------------
create table public.services (
    id                uuid primary key default gen_random_uuid(),
    tenant_id         uuid not null references public.tenants (id) on delete cascade,
    name              text not null check (char_length(name) between 1 and 120),
    duration_minutes  integer not null check (duration_minutes between 5 and 600),
    -- Prezzo in centesimi per evitare errori di arrotondamento.
    price_cents       integer check (price_cents >= 0),
    is_active         boolean not null default true,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),
    unique (id, tenant_id)
);

create index services_tenant_id_idx on public.services (tenant_id);

create trigger services_set_updated_at
    before update on public.services
    for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- business_hours: fasce di apertura (più fasce per giorno = pausa pranzo)
-- weekday: 0 = lunedì ... 6 = domenica (come datetime.weekday() in Python).
-- Orari espressi nel fuso del tenant (tenants.timezone).
-- -----------------------------------------------------------------------------
create table public.business_hours (
    id          uuid primary key default gen_random_uuid(),
    tenant_id   uuid not null references public.tenants (id) on delete cascade,
    weekday     smallint not null check (weekday between 0 and 6),
    open_time   time not null,
    close_time  time not null,
    created_at  timestamptz not null default now(),
    check (open_time < close_time)
);

create index business_hours_tenant_weekday_idx
    on public.business_hours (tenant_id, weekday);

-- -----------------------------------------------------------------------------
-- conversations: stato della chat per ogni numero cliente di ogni tenant
-- -----------------------------------------------------------------------------
create table public.conversations (
    id               uuid primary key default gen_random_uuid(),
    tenant_id        uuid not null references public.tenants (id) on delete cascade,
    customer_phone   text not null,
    customer_name    text,
    state            public.conversation_state not null default 'idle',
    mode             public.conversation_mode not null default 'ai',
    -- Fallimenti AI consecutivi; a 2 -> mode = 'manual' (gestito dal backend).
    failed_attempts  smallint not null default 0 check (failed_attempts >= 0),
    -- Dati parziali raccolti (servizio scelto, slot proposti, ecc.).
    context          jsonb not null default '{}'::jsonb,
    last_message_at  timestamptz,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    unique (tenant_id, customer_phone),
    unique (id, tenant_id)
);

create index conversations_tenant_last_msg_idx
    on public.conversations (tenant_id, last_message_at desc);

create trigger conversations_set_updated_at
    before update on public.conversations
    for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- messages: storico messaggi (anche per deduplica dei webhook)
-- -----------------------------------------------------------------------------
create table public.messages (
    id                   uuid primary key default gen_random_uuid(),
    tenant_id            uuid not null,
    conversation_id      uuid not null,
    direction            public.message_direction not null,
    body                 text not null,
    -- ID del provider (wamid / Twilio SID): l'unicità blocca i webhook duplicati.
    provider_message_id  text,
    created_at           timestamptz not null default now(),
    foreign key (conversation_id, tenant_id)
        references public.conversations (id, tenant_id) on delete cascade,
    unique (tenant_id, provider_message_id)
);

create index messages_conversation_created_idx
    on public.messages (conversation_id, created_at);

-- -----------------------------------------------------------------------------
-- bookings: appuntamenti confermati
-- -----------------------------------------------------------------------------
create table public.bookings (
    id               uuid primary key default gen_random_uuid(),
    tenant_id        uuid not null references public.tenants (id) on delete cascade,
    conversation_id  uuid,
    service_id       uuid,
    customer_phone   text not null,
    customer_name    text,
    starts_at        timestamptz not null,
    ends_at          timestamptz not null,
    status           public.booking_status not null default 'confirmed',
    google_event_id  text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    check (starts_at < ends_at),
    foreign key (conversation_id, tenant_id)
        references public.conversations (id, tenant_id)
        on delete set null (conversation_id),
    foreign key (service_id, tenant_id)
        references public.services (id, tenant_id)
        on delete set null (service_id),
    -- MVP con un solo calendario per tenant: niente sovrapposizioni tra
    -- prenotazioni confermate (protezione da doppie prenotazioni concorrenti).
    constraint bookings_no_overlap exclude using gist (
        tenant_id with =,
        tstzrange(starts_at, ends_at) with &&
    ) where (status = 'confirmed')
);

create index bookings_tenant_starts_idx on public.bookings (tenant_id, starts_at);

create trigger bookings_set_updated_at
    before update on public.bookings
    for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- google_credentials: OAuth Google Calendar per tenant.
-- Il refresh token è cifrato dal backend (Fernet, ENCRYPTION_KEY).
-- Nessuna policy RLS: accessibile solo con la service role key.
-- -----------------------------------------------------------------------------
create table public.google_credentials (
    id                       uuid primary key default gen_random_uuid(),
    tenant_id                uuid not null unique
                                 references public.tenants (id) on delete cascade,
    google_account_email     text,
    refresh_token_encrypted  text not null,
    calendar_id              text not null default 'primary',
    created_at               timestamptz not null default now(),
    updated_at               timestamptz not null default now()
);

create trigger google_credentials_set_updated_at
    before update on public.google_credentials
    for each row execute function public.set_updated_at();
