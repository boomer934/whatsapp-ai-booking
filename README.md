# Assistente WhatsApp per prenotazioni (MVP)

> **⚠️ Progetto in fase MVP – accesso solo su autorizzazione**
>
> Questo software è un **prototipo (MVP)** in fase di test, **non** un prodotto commerciale pronto all'uso.
> Il codice è pubblicato **solo a scopo di consultazione e portfolio**.
> **Solo le persone e le attività espressamente autorizzate dall'autore possono provare il servizio.**
> Non è consentito usarlo, installarlo, ridistribuirlo o offrirlo a terzi senza autorizzazione scritta (vedi [LICENSE](LICENSE)).

Micro-SaaS B2B che risponde ai clienti di attività locali (saloni, barbieri, officine, studi…) su **WhatsApp** e gestisce le **prenotazioni** in pochi messaggi, con passaggio a un operatore umano quando serve.

## Funzionalità

- Risposte automatiche su WhatsApp (Meta WhatsApp Cloud API) con interpretazione AI dei messaggi.
- Proposta degli orari liberi calcolata dal sistema (orari di apertura, prenotazioni esistenti, Google Calendar): **l'AI interpreta, ma non inventa disponibilità**.
- Prenotazione confermata e creazione dell'evento su Google Calendar.
- Passaggio automatico all'operatore (richiesta del cliente, messaggi non compresi, disdette) con notifica WhatsApp.
- Dashboard per il titolare: servizi, orari, conversazioni, prenotazioni, collegamento Google Calendar.
- Multi-tenant con isolamento dei dati a livello di database (Row Level Security).

## Architettura

| Componente | Tecnologia |
|---|---|
| Backend | Python, FastAPI |
| Dashboard | Next.js (App Router), TypeScript, Tailwind CSS |
| Database e autenticazione | Supabase (PostgreSQL + RLS) |
| AI | Groq (modello open-weight) per l'interpretazione dei messaggi |
| Messaggistica | WhatsApp Cloud API di Meta |
| Calendario | Google Calendar API (OAuth per attività) |

```
backend/    API FastAPI, webhook WhatsApp, logica di conversazione, test
frontend/   dashboard Next.js per i titolari
supabase/   migrazioni SQL e policy RLS
```

## Avvertenze

- **Stato MVP:** possono esserci bug, interruzioni del servizio e perdita di dati. Non usare per attività critiche.
- **Nessuna garanzia:** il software è fornito "così com'è", senza garanzie di alcun tipo.
- **Dati personali:** il servizio tratta dati dei clienti finali (numero di telefono, messaggi, prenotazioni). Il trattamento è descritto nell'[informativa privacy](https://whatsapp-ai-booking.vercel.app/privacy). Non inviare dati sanitari o altre categorie particolari di dati (art. 9 GDPR).
- **Intelligenza artificiale:** le risposte sono generate da un sistema automatico e il cliente ne viene informato al primo messaggio (Reg. UE 2024/1689, art. 50). Il cliente può sempre chiedere di parlare con una persona.
- **Servizi di terze parti:** il funzionamento dipende da Meta, Groq, Supabase, Render, Vercel e Google, soggetti ai rispettivi termini e limiti.
- **Configurazione:** il repository non contiene chiavi, token o credenziali. Senza le credenziali dell'autore il codice non è collegato a nessun servizio reale.

## Accesso e prove

Per richiedere l'accesso alla demo o segnalare un problema di sicurezza scrivi a **davide.webdeveloper934@gmail.com**.
Le vulnerabilità vanno segnalate privatamente via email, non tramite issue pubbliche.

## Licenza

© 2026 Davide Quadrotta. **Tutti i diritti riservati.** Vedi [LICENSE](LICENSE).
