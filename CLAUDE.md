# WhatsApp AI Booking SaaS - Contesto e Linee Guida del Progetto

## 1. Panoramica del Progetto

Micro-SaaS B2B che automatizza la qualificazione dei lead e la prenotazione degli appuntamenti su WhatsApp per attività commerciali locali (saloni di bellezza, autofficine, studi medici, ecc.). Obiettivo: prenotazione completata in massimo 3-4 scambi di messaggi.

- **Backend:** Python (FastAPI) su Render (piano Free) — blueprint in `render.yaml`.
- **Frontend:** Next.js + TypeScript + TailwindCSS su Vercel (piano Hobby) — *da realizzare (step 8)*.
- **Database e Autenticazione:** Supabase (PostgreSQL) con RLS.
- **Motore AI / LLM:** Groq `openai/gpt-oss-20b` (primario) con fallback automatico su Gemini `gemini-3.5-flash-lite`. I modelli Llama non sono più disponibili su Groq e `gemini-2.5-flash` non è attivabile per nuovi account: verificare sempre i modelli disponibili prima di cambiarli.
- **Integrazioni:** Twilio WhatsApp Sandbox (in uso per i test) / WhatsApp Cloud API di Meta (pronta, non ancora provata dal vivo), Google Calendar *(step 7)*.
- **Repository:** https://github.com/boomer934/whatsapp-ai-booking (privato, branch `main`).

## 2. Architettura e Principi di Progettazione

- **Multi-tenant:** ogni tabella di dominio ha `tenant_id`; le FK figlie usano la coppia `(id, tenant_id)` così il DB impedisce riferimenti cross-tenant. Il backend usa la chiave service (bypassa la RLS): **ogni query deve filtrare esplicitamente per `tenant_id`**. La dashboard userà la RLS (`is_tenant_member`) e i privilegi di colonna definiti in `0002_rls_policies.sql`.
- **Vincolo 100% piano gratuito:** nessun costo fisso nell'MVP. Limiti noti: Groq free ≈ 8.000 token/minuto (≈ 6 messaggi/minuto con il prompt attuale); Gemini free ha picchi di errori 503. Il fallback tra i due copre i picchi.
- **L'LLM interpreta, il codice risponde:** l'LLM restituisce solo JSON strutturato (intent, servizio, data, ora, slot scelto) validato campo per campo in `interpreter.py`. Proposte di orario, conferme e prenotazioni sono testi da template in `state_machine.py`: l'AI non può inventare disponibilità. L'LLM scrive testo libero solo per domande informative e saluti, basandosi sui dati dell'attività.
- **Risposte brevi e concise:** massimo 1-2 domande per messaggio, niente markdown.
- **Fallback handover umano:** dopo 2 messaggi consecutivi non compresi (o errori LLM), oppure su richiesta del cliente / disdette / domande fuori dai dati, la conversazione passa a `mode = manual`, il bot smette di rispondere e l'operatore (`tenants.operator_phone`) riceve una notifica WhatsApp.
- **Webhook:** rispondono subito 200 ed elaborano in `BackgroundTasks` (cold start di Render). Firme verificate (Meta HMAC-SHA256, Twilio HMAC-SHA1); in `development` con segreto vuoto la verifica viene saltata con warning, in `production` la richiesta viene rifiutata. Deduplica tramite unique `(tenant_id, provider_message_id)`.
- **Disponibilità:** orari di apertura (`business_hours`, 0 = lunedì) meno prenotazioni confermate; slot ogni 30 minuti, preavviso minimo 60 minuti, orizzonte 14 giorni. Il vincolo `bookings_no_overlap` protegge dalle doppie prenotazioni concorrenti (un calendario per tenant).

## 3. Struttura del Progetto

```
/
├── backend/
│   ├── app/
│   │   ├── api/            # router.py, deps.py (composizione dipendenze), routes/ (health, webhook_meta, webhook_twilio)
│   │   ├── core/           # config.py (pydantic-settings), db.py (client Supabase async), security.py (firme webhook)
│   │   ├── models/         # enums.py, schemas.py (Pydantic)
│   │   ├── repositories/   # base.py (Protocol ConversationStore), supabase_store.py
│   │   └── services/
│   │       ├── llm/            # groq_client, gemini_client, factory (fallback), prompts
│   │       ├── messaging/      # meta_whatsapp, twilio_whatsapp, factory
│   │       ├── conversation/   # inbound (pipeline), state_machine, interpreter, context, formatting
│   │       ├── calendar/       # availability (Google Calendar nello step 7)
│   │       └── notifications.py
│   ├── tests/              # pytest; fakes.py con store/LLM/sender in memoria
│   ├── main.py
│   ├── requirements.txt / requirements-dev.txt
│   └── .env.example
├── frontend/               # (step 8) Next.js App Router
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

**Test WhatsApp in locale (Twilio Sandbox)**

1. Tunnel: `cloudflared tunnel --url http://localhost:8000` (quick tunnel, nessun account; l'URL cambia a ogni avvio).
2. Avviare il backend con `PUBLIC_BASE_URL=<url del tunnel>` (necessario per la verifica firma Twilio dietro proxy).
3. Console Twilio > Messaging > Try it out > WhatsApp sandbox settings: "When a message comes in" = `<url del tunnel>/webhooks/twilio` (POST).

**Frontend (Next.js / TypeScript)** — dallo step 8

- `cd frontend && npm install`, `npm run dev`, `npm run build`

## 5. Configurazione (`backend/.env`, mai committato)

- Copiare `backend/.env.example` in `backend/.env`. **Le chiavi vanno solo in `.env`**, `.env.example` resta senza valori.
- `SUPABASE_URL` = URL base del progetto (`https://<ref>.supabase.co`); un eventuale `/rest/v1/` viene rimosso automaticamente.
- `SUPABASE_SERVICE_ROLE_KEY` accetta la chiave legacy `service_role` o la nuova `sb_secret_...`. Solo lato server.
- `GROQ_REASONING_EFFORT` (per gpt-oss) e `GEMINI_THINKING_LEVEL` (per Gemini 3, `minimal` = più veloce) riducono la latenza.
- Python locale 3.14 / Render 3.12: mantenere il codice compatibile con 3.12. `tzdata` è richiesto su Windows per `zoneinfo`.

## 6. Standard di Codifica e Linee Guida

- **Python:** PEP 8, type hint ovunque (mypy deve passare), Pydantic per la validazione. Le dipendenze esterne (store, LLM, sender, notifier) sono iniettate tramite Protocol: nei test usare i fake di `backend/tests/fakes.py`, mai servizi reali.
- **TypeScript:** modalità strict, niente `any`, componenti funzionali React con classi Tailwind standard.
- **Database:** migrazioni pulite e documentate in `supabase/migrations/`, numerate in sequenza; UUID come chiavi primarie; mantenere allineati gli enum SQL con `backend/app/models/enums.py`.
- **Git:** commit in italiano con prefissi convenzionali (`feat:`, `fix:`, `chore:`); push su `origin/main` dopo ogni commit. Prima di ogni commit verificare che nessun segreto sia nei file in stage.

## 7. Stato di Avanzamento

- [x] Step 1-3: scaffold, backend base, schema Supabase + RLS (migrazioni applicate sul progetto Supabase, seed inserito)
- [x] Step 4: webhook Meta/Twilio con verifica firma e deduplica
- [x] Step 5-6: interpretazione AI, macchina a stati, disponibilità, handover — verificati con LLM e DB reali
- [ ] Step 7: Google Calendar (OAuth per tenant, free/busy, creazione evento alla conferma)
- [ ] Step 8: dashboard Next.js (servizi, orari, toggle AI, chat in manuale, prenotazioni)
- [ ] Step 9: deploy Render + Vercel e webhook definitivi
- Da fare prima della produzione: template WhatsApp approvato per le notifiche all'operatore (finestra di 24h di Meta); gestione disdette/spostamenti (oggi vanno all'operatore).
