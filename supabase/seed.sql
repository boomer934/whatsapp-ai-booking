-- =============================================================================
-- seed.sql — dati demo per sviluppo locale/test (NON eseguire in produzione).
-- Per collegare il tuo utente alla dashboard, dopo la registrazione esegui:
--   insert into public.tenant_members (tenant_id, user_id, role)
--   values ('00000000-0000-0000-0000-000000000001', '<auth.users.id>', 'owner');
-- =============================================================================

insert into public.tenants (id, name, timezone, messaging_provider, wa_phone_number_id, wa_phone_e164, operator_phone)
values (
    '00000000-0000-0000-0000-000000000001',
    'Salone Demo',
    'Europe/Rome',
    'twilio',
    null,
    '+14155238886',          -- numero del Twilio WhatsApp Sandbox
    '+390000000000'          -- sostituisci con il numero dell'operatore
);

insert into public.services (tenant_id, name, duration_minutes, price_cents) values
    ('00000000-0000-0000-0000-000000000001', 'Taglio donna', 45, 3500),
    ('00000000-0000-0000-0000-000000000001', 'Taglio uomo', 30, 2000),
    ('00000000-0000-0000-0000-000000000001', 'Piega', 30, 2500),
    ('00000000-0000-0000-0000-000000000001', 'Colore', 90, 6000);

-- Mar-Sab 09:00-13:00 e 14:30-19:00 (0 = lunedì).
insert into public.business_hours (tenant_id, weekday, open_time, close_time)
select '00000000-0000-0000-0000-000000000001', d, t.open_time, t.close_time
from generate_series(1, 5) as d
cross join (values ('09:00'::time, '13:00'::time), ('14:30'::time, '19:00'::time))
    as t (open_time, close_time);
