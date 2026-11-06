# WhatsApp AI Booking SaaS - Contesto e Linee Guida del Progetto

## 1. Panoramica del Progetto

Micro-SaaS B2B che automatizza la qualificazione dei lead e la prenotazione degli appuntamenti su WhatsApp per attività commerciali locali (saloni di bellezza, autofficine, studi medici, ecc.). Obiettivo: prenotazione completata in massimo 3-4 scambi di messaggi.

- **Backend:** Python (FastAPI) su Render (piano Free) — blueprint in `render.yaml`.
- **Frontend:** Next.js 16 (App Router, Cache Components) + TypeScript strict + Tailwind v4 su Vercel (piano Hobby) — dashboard per i titolari in `frontend/`.
- **Database e Autenticazione:** Supabase (PostgreSQL) con RLS.
- **Motore AI / LLM:** Groq `openai/gpt-oss-20b` (primario) con fallback automatico su Gemini `gemini-3.5-flash-lite`. I modelli Llama non sono più disponibili su Groq e `gemini-2.5-flash` non è attivabile per nuovi account: verificare sempre i modelli disponibili prima di cambiarli.
- **Integrazioni:** WhatsApp Cloud API di Meta (canale scelto: numero di test gratuito, risposte entro 24h gratuite; configurazione in corso) / Twilio (supportato ma a pagamento, non usato), Google Calendar via OAuth per tenant.
- **Repository:** https://github.com/boomer934/whatsapp-ai-booking (privato, branch `main`).
- **Produzione:** backend https://whatsapp-ai-booking-syjn.onrender.com (Render, Web Service Free, deploy automatico da `main`), dashboard https://whatsapp-ai-booking.vercel.app (Vercel Hobby, Root Directory `frontend`, deploy automatico da `main`). Stesso progetto Supabase dell'ambiente locale.

## 2. Architettura e Principi di Progettazione

- **Multi-tenant:** ogni tabella di dominio ha `tenant_id`; le FK figlie usano la coppia `(id, tenant_id)` così il DB impedisce riferimenti cross-tenant. Il backend usa la chiave service (bypassa la RLS): **ogni query deve filtrare esplicitamente per `tenant_id`**. La dashboard usa la RLS (`is_tenant_member`) e i privilegi di colonna definiti in `0002_rls_policies.sql`.
- **Vincolo 100% piano gratuito:** nessun costo fisso nell'MVP. Limiti noti: Groq free ≈ 8.000 token/minuto (≈ 6 messaggi/minuto con il prompt attuale); Gemini free ha picchi di errori 503. Il fallback tra i due copre i picchi.
- **L'LLM interpreta, il codice risponde:** l'LLM restituisce solo JSON strutturato (intent, servizio, data, ora, slot scelto) validato campo per campo in `interpreter.py`. Proposte di orario, conferme e prenotazioni sono testi da template in `state_machine.py`: l'AI non può inventare disponibilità. L'LLM scrive testo libero solo per domande informative e saluti, basandosi sui dati dell'attività.
- **Risposte brevi e concise:** massimo 1-2 domande per messaggio, niente markdown.
- **Trasparenza e privacy:** la prima risposta a ogni cliente include l'avviso "assistente automatico" (AI Act art. 50) e il link a `{FRONTEND_URL}/privacy` (`ai_disclosure` in `inbound.py`). L'informativa pubblica è `frontend/src/app/privacy/page.tsx`: aggiornarla quando cambiano dati trattati, fornitori o conservazione. Niente LLM che usano i contenuti per addestramento (per questo Gemini free è disattivato in produzione).
- **Fallback handover umano:** dopo 2 messaggi consecutivi non compresi (o errori LLM), oppure su richiesta del cliente / disdette / domande fuori dai dati, la conversazione passa a `mode = manual`, il bot smette di rispondere e l'operatore (`tenants.operator_phone`) riceve una notifica WhatsApp.
- **Webhook:** rispondono subito 200 ed elaborano in `BackgroundTasks` (cold start di Render). Firme verificate (Meta HMAC-SHA256, Twilio HMAC-SHA1); in `development` con segreto vuoto la verifica viene saltata con warning, in `production` la richiesta viene rifiutata. Deduplica tramite unique `(tenant_id, provider_message_id)`.
- **Disponibilità:** orari di apertura (`business_hours`, 0 = lunedì) meno prenotazioni confermate meno impegni Google Calendar (`CombinedBusyProvider`); slot ogni 30 minuti, preavviso minimo 60 minuti, orizzonte 14 giorni. Lo slot viene ricontrollato subito prima di prenotare. Il vincolo `bookings_no_overlap` protegge dalle doppie prenotazioni concorrenti (un calendario per tenant).
- **Google Calendar:** OAuth per tenant con scope minimi (`calendar.events` + `calendar.freebusy`). Refresh token cifrato con Fernet (`ENCRYPTION_KEY`) in `google_credentials` (tabella senza policy RLS: solo backend). Lo `state` OAuth è un token Fernet con scadenza 10 minuti che contiene tenant e utente. **Fail-closed**: se il calendario è collegato ma Google non risponde, niente orari proposti e handover all'operatore. La creazione dell'evento dopo la conferma non blocca mai la prenotazione (il DB è la fonte di verità; `google_event_id` salvato sulla prenotazione).
- **API della dashboard:** `Authorization: Bearer <access token Supabase>` verificato con Supabase Auth (`api/auth.py`), poi `require_tenant_member` controlla `tenant_members`. Endpoint: `GET/DELETE /api/tenants/{id}/google`, `POST /api/tenants/{id}/google/connect`, `POST /api/tenants/{id}/bookings/{booking_id}/cancel` (idempotente: annulla e rimuove l'evento Google, che non blocca mai l'annullamento); callback pubblico `GET /oauth/google/callback` che reindirizza a `{FRONTEND_URL}/dashboard/settings?google=connected|error&reason=…`.
- **Accesso solo su autorizzazione:** registrazioni disattivate su Supabase (`disable_signup`) e niente modulo di registrazione: gli account si creano da Supabase > Authentication > Users > Add user (con "Auto confirm"), poi il titolare accede e fa l'onboarding.
- **Dashboard (frontend):** legge e scrive direttamente su Supabase con la chiave publishable e la sessione dell'utente, quindi è protetta dalla RLS e dai privilegi di colonna (il routing WhatsApp `wa_*`/`messaging_provider` non è modificabile dal titolare). Chiama il backend solo per ciò che richiede segreti (Google Calendar, annullamento con rimozione evento), passando il Bearer token. Ogni pagina e Server Action verifica sessione e membership lato server (`lib/dal.ts`); `src/proxy.ts` (il "middleware" di Next 16) rinnova la sessione e reindirizza al login.

## 3. Struttura del Progetto

```
/
├── backend/
│   ├── app/
│   │   ├── api/            # router.py, deps.py (composizione dipendenze), auth.py (token Supabase + membership), routes/ (health, webhook_meta, webhook_twilio, google_calendar, bookings)
│   │   ├── core/           # config.py (pydantic-settings), db.py (client Supabase async), security.py (firme webhook), crypto.py (Fernet)
│   │   ├── models/         # enums.py, schemas.py (Pydantic)
│   │   ├── repositories/   # base.py (Protocol ConversationStore), supabase_store.py, tenant_admin.py (membership + credenziali Google)
│   │   ├── simulator/      # simulatore WhatsApp locale: service.py, store.py, static/index.html
│   │   └── services/
│   │       ├── llm/            # groq_client, gemini_client, factory (fallback), prompts
│   │       ├── messaging/      # meta_whatsapp, twilio_whatsapp, factory
│   │       ├── conversation/   # inbound (pipeline), state_machine, interpreter, context, formatting
│   │       ├── calendar/       # availability, google_client (HTTP OAuth/Calendar v3), google_calendar (servizio per tenant)
│   │       └── notifications.py
│   ├── tests/              # pytest; fakes.py (store/LLM/sender in memoria), google_fake.py (finto server Google)
│   ├── main.py
│   ├── requirements.txt / requirements-dev.txt
│   └── .env.example
├── frontend/               # Next.js 16 App Router (AGENTS.md: leggere node_modules/next/dist/docs prima di scrivere codice)
│   └── src/
│       ├── proxy.ts        # rinnovo sessione Supabase + protezione rotte
│       ├── app/            # login/, auth/callback/, onboarding/, dashboard/{page, services, hours, conversations, bookings, settings}
│       ├── components/     # ui.tsx (Card, Badge, …), form-controls.tsx (SubmitButton, FormMessage, useFormAction)
│       └── lib/            # supabase/{server,proxy}.ts, dal.ts (sessione + attività corrente), backend.ts (fetch con Bearer), database.types.ts
├── supabase/
│   ├── migrations/         # 0001_init_schema.sql, 0002_rls_policies.sql
│   └── seed.sql            # tenant demo collegato al Twilio Sandbox (+14155238886)
├── render.yaml
└── CLAUDE.md
```

## 4. Comandi di Sviluppo e Setup

Tutti i comandi si lanciano dalla radice del repository (gli import sono `backend.app...`).

**Backend (Python / FastAPI)**

- Ambiente virtuale: `python -m venv venv` poi `venv\Scripts\activate` (Windows) o `source venv/bin/activate`
- Dipendenze: `pip install -r backend/requirements-dev.txt`
- Server locale: `uvicorn backend.main:app --reload --port 8000`
- Test: `python -m pytest backend/tests -q`
- Type check: `python -m mypy backend/app backend/main.py --ignore-missing-imports`

**Simulatore WhatsApp (metodo principale per i test end-to-end)**

1. Avviare il backend: `uvicorn backend.main:app --reload --port 8000`.
2. Aprire `http://localhost:8000/simulator`: chat in stile WhatsApp + pannello con stato, prenotazioni, notifiche all'operatore, "Riprendi AI" e reset.
   Il riquadro "Google Calendar" collega/scollega il calendario del tenant (flusso OAuth di sviluppo, accettato solo con simulatore attivo). Dopo aver modificato `backend/.env` riavviare uvicorn: `--reload` non rilegge il file.
3. Usa la pipeline reale (LLM, Supabase, Google Calendar); solo l'invio è catturato (`MessagingProviderName.SIMULATOR`, instradamento per `tenant_id`). Nessun messaggio reale parte, nemmeno verso l'operatore.
4. Attivo solo se `ENVIRONMENT != production` e `SIMULATOR_ENABLED=true`; accetta solo richieste locali (rifiuta header di proxy/tunnel). Usare numeri cliente di test (`+3900000000xx`) e il reset per pulire.

**Test WhatsApp reale in locale (Twilio Sandbox — a pagamento, alternativa: Meta Cloud API)**

1. Tunnel: `cloudflared tunnel --url http://localhost:8000` (quick tunnel, nessun account; l'URL cambia a ogni avvio).
2. Avviare il backend con `PUBLIC_BASE_URL=<url del tunnel>` (necessario per la verifica firma Twilio dietro proxy).
3. Console Twilio > Messaging > Try it out > WhatsApp sandbox settings: "When a message comes in" = `<url del tunnel>/webhooks/twilio` (POST).

**Deploy**

- Render: Web Service dal repo, build `pip install -r requirements.txt` (il `requirements.txt` in radice include `backend/requirements.txt`; Python fissato da `.python-version`), start `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, health check `/health`. Variabili come `backend/.env` ma con `ENVIRONMENT=production`, `SIMULATOR_ENABLED=false`, `PUBLIC_BASE_URL`/`GOOGLE_REDIRECT_URI` sull'URL Render e `FRONTEND_URL` sull'URL Vercel. Il piano Free si sospende dopo 15 minuti (risveglio ~50 s).
- Vercel: Root Directory `frontend`, variabili `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `API_URL` (URL Render).
- Il test E2E si può puntare alla produzione con `FRONT_URL=https://whatsapp-ai-booking.vercel.app` (le conversazioni passano comunque dal simulatore locale, che scrive sullo stesso DB).

**Frontend (Next.js / TypeScript)**

- `cd frontend && npm install`, poi `npm run dev` (oppure `npm run build && npx next start`).
- Controlli: `npx tsc --noEmit`, `npx eslint src`, `npm run build`.
- In locale la porta 3000 è occupata da Docker Desktop: usare `-p 3001` (`npx next dev -p 3001`). Per OAuth Google dalla dashboard locale impostare `FRONTEND_URL=http://localhost:3001` in `backend/.env`.
- Test E2E: script Playwright (Python, nel venv) che crea un utente/attività di test via API admin, percorre tutte le pagine (anche una conversazione reale dal simulatore e i controlli RLS) e poi cancella tutto. Con Cache Components le pagine già visitate restano nel DOM nascoste (`<Activity>`): nei locator usare `:visible` o `get_by_role`, mai selettori generici come `li` o `main`.
- Next 16: `cookies()`, `searchParams` e l'ora corrente vanno letti dentro `<Suspense>`; dopo una mutazione usare `refresh()` di `next/cache`; `error.tsx` riceve `retry`. Non affidare messaggi una tantum a query string dopo un `redirect()` da Server Action (il router può riusare i dati prefetchati senza parametri): ricavarli dallo stato.

## 5. Configurazione (`backend/.env`, mai committato)

- Copiare `backend/.env.example` in `backend/.env`. **Le chiavi vanno solo in `.env`**, `.env.example` resta senza valori.
- `SUPABASE_URL` = URL base del progetto (`https://<ref>.supabase.co`); un eventuale `/rest/v1/` viene rimosso automaticamente.
- `SUPABASE_SERVICE_ROLE_KEY` accetta la chiave legacy `service_role` o la nuova `sb_secret_...`. Solo lato server.
- `ENCRYPTION_KEY` (Fernet) è obbligatoria per Google Calendar: usare la stessa chiave in tutti gli ambienti che condividono il DB, altrimenti i calendari collegati vanno ricollegati.
- Google OAuth: client "Applicazione web" in Google Cloud Console con Calendar API abilitata; `GOOGLE_REDIRECT_URI` deve coincidere esattamente con un redirect autorizzato. Con la schermata di consenso in modalità "Test" servono gli utenti di test; la pubblicazione richiede la verifica Google (scope sensibili).
- `GROQ_REASONING_EFFORT` (per gpt-oss) e `GEMINI_THINKING_LEVEL` (per Gemini 3, `minimal` = più veloce) riducono la latenza.
- Frontend: copiare `frontend/.env.example` in `frontend/.env.local` (mai committato): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (chiave `sb_publishable_...`, pubblica per natura) e `API_URL` (backend, letto solo lato server).
- Python locale 3.14 / Render 3.12: mantenere il codice compatibile con 3.12. `tzdata` è richiesto su Windows per `zoneinfo`.

## 6. Standard di Codifica e Linee Guida

- **Python:** PEP 8, type hint ovunque (mypy deve passare), Pydantic per la validazione. Le dipendenze esterne (store, LLM, sender, notifier, calendario) sono iniettate tramite Protocol: nei test usare i fake di `backend/tests/`, mai servizi reali.
- **Script di verifica dal vivo:** il client Supabase async è condiviso e legato a un event loop; negli script che chiamano l'app usare `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` nello stesso loop, non `TestClient`. Usare numeri/utenti di test dedicati e cancellarli alla fine.
- **TypeScript:** modalità strict, niente `any`, componenti funzionali React con classi Tailwind standard.
- **Database:** migrazioni pulite e documentate in `supabase/migrations/`, numerate in sequenza; UUID come chiavi primarie; mantenere allineati gli enum SQL con `backend/app/models/enums.py`.
- **Git:** commit in italiano con prefissi convenzionali (`feat:`, `fix:`, `chore:`); push su `origin/main` dopo ogni commit. Prima di ogni commit verificare che nessun segreto sia nei file in stage.

## 7. Stato di Avanzamento

- [x] Step 1-3: scaffold, backend base, schema Supabase + RLS (migrazioni applicate sul progetto Supabase, seed inserito)
- [x] Step 4: webhook Meta/Twilio con verifica firma e deduplica
- [x] Step 5-6: interpretazione AI, macchina a stati, disponibilità, handover — verificati con LLM e DB reali
- [x] Step 7: Google Calendar (OAuth per tenant, free/busy, evento alla conferma) — verificato con account Google reale: collegamento dal simulatore, lettura free/busy ed evento creato alla prenotazione. Client OAuth di sviluppo in modalità "Test" (redirect `http://localhost:8000/oauth/google/callback`); in produzione servirà un redirect URI del backend su Render e la verifica dell'app Google.
- [x] Step 8: dashboard Next.js (login/registrazione, onboarding, panoramica con checklist, servizi, orari con più fasce, toggle AI, conversazioni con "Riprendi AI", prenotazioni con annullamento, impostazioni e collegamento Google) — verificata end-to-end con Playwright (41/41 controlli, inclusi RLS e privilegi di colonna)
- [x] Step 9: deploy Render + Vercel — verificato con il test E2E Playwright contro la produzione (41/41). In produzione: `ENVIRONMENT=production`, `SIMULATOR_ENABLED=false`, `/docs` e `/openapi.json` disattivati, webhook senza firma rifiutati; redirect URI Google di produzione aggiunto al client OAuth. L'app rifiuta di avviarsi in production se la configurazione è incompleta (`Settings.production_problems()`, motivo nei log di Render).
- [x] WhatsApp Meta Cloud API (numero di test): app Meta "Assistenza prenotazioni" (id 1104236002216930, non pubblicata), numero di test +1 555 161 4601 (Phone Number ID 1427890947074724, WABA 2206727593586658) collegato al tenant "Davide parrucchiere" (account davide.webdeveloper934@gmail.com, Google Calendar collegato); webhook `https://whatsapp-ai-booking-syjn.onrender.com/webhooks/meta` con `META_*` su Render. Verificato con un messaggio reale. Attenzione: l'app va iscritta alla WABA (`POST /{WABA_ID}/subscribed_apps`), altrimenti Meta non inoltra i messaggi anche con il webhook verificato. Max 5 numeri destinatari sul numero di test.
- [x] Token permanente di "utente di sistema" in `META_ACCESS_TOKEN` su Render; prenotazione completa verificata su WhatsApp reale.
- [x] Simulatore WhatsApp locale per test end-to-end senza provider (verificato con AI e DB reali)
- Da fare prima della produzione: template WhatsApp approvato per le notifiche all'operatore (finestra di 24h di Meta); gestione disdette/spostamenti (oggi vanno all'operatore); **soggetto giuridico verificabile (es. partita IVA) per la verifica business Meta e l'App Review necessarie all'onboarding dei clienti (Embedded Signup)**; test WhatsApp reale con numero di test Meta.
