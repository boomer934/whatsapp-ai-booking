WhatsApp AI Booking SaaS - Contesto e Linee Guida del Progetto

1. Panoramica del Progetto

Questo progetto è un Micro-SaaS B2B che automatizza la qualificazione dei lead e la prenotazione degli appuntamenti su WhatsApp per attività commerciali locali (saloni di bellezza, autofficine, studi medici, ecc.).

Backend: Python (FastAPI) ospitato su Render (Piano Gratuito).

Frontend: Next.js + TypeScript (React) con TailwindCSS, ospitato su Vercel (Piano Hobby).

Database e Autenticazione: Supabase (PostgreSQL).

Motore AI / LLM: API Groq (Llama 3.1) o API Google Gemini Flash (Piano gratuito per sviluppatori).

Integrazioni: API WhatsApp Cloud di Meta / Twilio Sandbox, API Google Calendar.

2. Architettura e Principi di Progettazione

Sistema Multi-Tenant: Assicurati che tutti gli schemi del database (tenants, conversations, bookings) isolino correttamente i dati tra i diversi clienti aziendali.

Vincolo 100% Piano Gratuito: L'architettura deve basarsi strettamente sui piani gratuiti e azzerare i costi fissi durante la fase di MVP.

Risposte Brevi e Concise: I messaggi WhatsApp devono essere brevi, cordiali e diretti (massimo 1-2 domande alla volta).

Fallback Handover Umano: Se l'AI non riesce a interpretare l'intenzione dell'utente per due volte di seguito, passa la conversazione alla modalità manuale e notifica l'operatore dell'attività.

3. Struttura del Progetto Consigliata

/
├── backend/                # Applicazione FastAPI
│   ├── app/
│   │   ├── api/            # Gestione delle rotte (webhook, endpoint API)
│   │   ├── core/           # Configurazione, sicurezza, connessione al DB
│   │   ├── services/       # Logica AI, client WhatsApp, API Google Calendar
│   │   └── models/         # Modelli Pydantic & SQLAlchemy/Supabase
│   ├── main.py
│   └── requirements.txt
├── frontend/               # Dashboard Next.js in TypeScript
│   ├── src/
│   │   ├── app/            # Pagine App Router di Next.js
│   │   ├── components/     # Componenti React
│   │   └── lib/            # Client Supabase, funzioni di utilità
│   └── package.json
├── CLAUDE.md
└── .claudeignore


4. Comandi di Sviluppo e Setup

Backend (Python / FastAPI)

Configurazione Ambiente Virtuale: python -m venv venv && source venv/bin/activate (o venv\Scripts\activate su Windows)

Installazione Dipendenze: pip install -r backend/requirements.txt

Avvio Server Locale: uvicorn backend.main:app --reload --port 8000

Frontend (Next.js / TypeScript)

Installazione Dipendenze: cd frontend && npm install

Avvio Server di Sviluppo: npm run dev

Build del Progetto: npm run build

5. Standard di Codifica e Linee Guida

Python: Segui le linee guida PEP 8. Usa esplicitamente i Type Hint ovunque. Usa Pydantic per la validazione dei dati.

TypeScript: Abilita la modalità strict. Evita l'uso di any. Usa componenti funzionali React con le classi di utilità standard di Tailwind CSS.

Database: Mantieni gli script di migrazione puliti e ben documentati. Usa sempre gli UUID per le chiavi primarie.