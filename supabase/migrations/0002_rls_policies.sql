-- =============================================================================
-- 0002_rls_policies.sql
-- Row Level Security: un utente autenticato vede/modifica solo i dati dei
-- tenant di cui è membro (tenant_members). Il backend usa la service role key
-- e bypassa la RLS, quindi deve sempre filtrare per tenant_id da codice.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Helper: l'utente corrente è membro del tenant?
-- SECURITY DEFINER evita la ricorsione RLS su tenant_members.
-- -----------------------------------------------------------------------------
create or replace function public.is_tenant_member(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.tenant_members tm
        where tm.tenant_id = p_tenant_id
          and tm.user_id = (select auth.uid())
    );
$$;

revoke execute on function public.is_tenant_member(uuid) from public, anon;
grant execute on function public.is_tenant_member(uuid) to authenticated;

-- -----------------------------------------------------------------------------
-- Onboarding: crea un tenant e rende owner l'utente corrente (atomico).
-- -----------------------------------------------------------------------------
create or replace function public.create_tenant(p_name text, p_timezone text default 'Europe/Rome')
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_user_id   uuid := auth.uid();
    v_tenant_id uuid;
begin
    if v_user_id is null then
        raise exception 'Autenticazione richiesta';
    end if;

    insert into public.tenants (name, timezone)
    values (p_name, p_timezone)
    returning id into v_tenant_id;

    insert into public.tenant_members (tenant_id, user_id, role)
    values (v_tenant_id, v_user_id, 'owner');

    return v_tenant_id;
end;
$$;

revoke execute on function public.create_tenant(text, text) from public, anon;
grant execute on function public.create_tenant(text, text) to authenticated;

-- -----------------------------------------------------------------------------
-- Abilitazione RLS su tutte le tabelle
-- -----------------------------------------------------------------------------
alter table public.tenants            enable row level security;
alter table public.tenant_members     enable row level security;
alter table public.services           enable row level security;
alter table public.business_hours     enable row level security;
alter table public.conversations      enable row level security;
alter table public.messages           enable row level security;
alter table public.bookings           enable row level security;
alter table public.google_credentials enable row level security;
-- google_credentials: nessuna policy => inaccessibile ad anon/authenticated.

-- -----------------------------------------------------------------------------
-- Privilegi di colonna: la dashboard può modificare solo i campi "di business".
-- Routing WhatsApp (wa_phone_number_id, ...) e stato AI sono gestiti dal backend.
-- -----------------------------------------------------------------------------
revoke insert, update, delete on public.tenants from anon, authenticated;
grant update (name, timezone, ai_enabled, operator_phone)
    on public.tenants to authenticated;

revoke insert, update, delete on public.tenant_members from anon, authenticated;

revoke insert, update, delete on public.conversations from anon, authenticated;
-- Ripresa manuale -> AI dalla dashboard.
grant update (mode, failed_attempts) on public.conversations to authenticated;

revoke insert, update, delete on public.messages from anon, authenticated;

revoke insert, update, delete on public.bookings from anon, authenticated;
grant update (status) on public.bookings to authenticated;

revoke all on public.google_credentials from anon, authenticated;

-- -----------------------------------------------------------------------------
-- Policy
-- -----------------------------------------------------------------------------

-- tenants
create policy tenants_select on public.tenants
    for select to authenticated
    using (public.is_tenant_member(id));

create policy tenants_update on public.tenants
    for update to authenticated
    using (public.is_tenant_member(id))
    with check (public.is_tenant_member(id));

-- tenant_members
create policy tenant_members_select on public.tenant_members
    for select to authenticated
    using (public.is_tenant_member(tenant_id));

-- services (CRUD completo dalla dashboard)
create policy services_all on public.services
    for all to authenticated
    using (public.is_tenant_member(tenant_id))
    with check (public.is_tenant_member(tenant_id));

-- business_hours (CRUD completo dalla dashboard)
create policy business_hours_all on public.business_hours
    for all to authenticated
    using (public.is_tenant_member(tenant_id))
    with check (public.is_tenant_member(tenant_id));

-- conversations
create policy conversations_select on public.conversations
    for select to authenticated
    using (public.is_tenant_member(tenant_id));

create policy conversations_update on public.conversations
    for update to authenticated
    using (public.is_tenant_member(tenant_id))
    with check (public.is_tenant_member(tenant_id));

-- messages (sola lettura; scritti dal backend)
create policy messages_select on public.messages
    for select to authenticated
    using (public.is_tenant_member(tenant_id));

-- bookings
create policy bookings_select on public.bookings
    for select to authenticated
    using (public.is_tenant_member(tenant_id));

create policy bookings_update on public.bookings
    for update to authenticated
    using (public.is_tenant_member(tenant_id))
    with check (public.is_tenant_member(tenant_id));
