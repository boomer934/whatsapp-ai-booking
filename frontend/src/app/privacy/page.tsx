import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "Informativa sulla privacy" };

// Dati del fornitore del servizio (titolare per gli account, responsabile per i clienti finali).
const PROVIDER_NAME = "Davide Quadrotta";
const CONTACT_EMAIL = "davide.webdeveloper934@gmail.com";
const LAST_UPDATED = "6 novembre 2026";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <div className="space-y-3 text-sm leading-6 text-slate-700">{children}</div>
    </section>
  );
}

function Mail() {
  return (
    <a className="font-medium text-emerald-700 underline" href={`mailto:${CONTACT_EMAIL}`}>
      {CONTACT_EMAIL}
    </a>
  );
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <div className="space-y-10 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">Informativa sulla privacy</h1>
          <p className="text-sm text-slate-500">
            Assistente WhatsApp per prenotazioni · Ultimo aggiornamento: {LAST_UPDATED}
          </p>
          <p className="text-sm leading-6 text-slate-700">
            Questa informativa è resa ai sensi degli artt. 13 e 14 del Regolamento (UE) 2016/679
            (&quot;GDPR&quot;) e del D.Lgs. 196/2003 (Codice in materia di protezione dei dati
            personali) e spiega come vengono trattati i dati personali nell&apos;ambito del servizio
            &quot;Assistente WhatsApp&quot;, un software che consente ad attività locali (saloni,
            officine, studi, ecc.) di rispondere ai clienti e gestire le prenotazioni su WhatsApp.
          </p>
        </header>

        <Section title="1. Chi tratta i tuoi dati">
          <p>
            Il servizio è fornito da <strong>{PROVIDER_NAME}</strong> (di seguito &quot;il
            Fornitore&quot;), contattabile all&apos;indirizzo <Mail />.
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Se scrivi su WhatsApp a un&apos;attività</strong> che usa il servizio, il
              titolare del trattamento è <strong>l&apos;attività a cui scrivi</strong>. Il Fornitore
              tratta i tuoi dati solo per suo conto e secondo le sue istruzioni, come responsabile
              del trattamento ai sensi dell&apos;art. 28 GDPR.
            </li>
            <li>
              <strong>Se usi la dashboard</strong> come titolare o collaboratore di
              un&apos;attività, il titolare del trattamento dei dati del tuo account è il Fornitore.
            </li>
          </ul>
        </Section>

        <Section title="2. Quali dati trattiamo">
          <p>
            <strong>Clienti che scrivono su WhatsApp:</strong> numero di telefono, nome del profilo
            WhatsApp, testo dei messaggi scambiati con l&apos;assistente e con l&apos;attività, dati
            delle prenotazioni (servizio, data, orario, stato) e lo stato tecnico della
            conversazione. Allegati come foto o audio non vengono analizzati.
          </p>
          <p>
            <strong>Titolari e collaboratori delle attività:</strong> indirizzo email e password
            (conservata dal fornitore di autenticazione solo in forma cifrata non reversibile), dati
            dell&apos;attività (nome, servizi, orari, numero di telefono dell&apos;operatore) e, se
            l&apos;attività collega Google Calendar, l&apos;indirizzo email dell&apos;account Google,
            un token di autorizzazione conservato cifrato, gli intervalli di occupato/libero del
            calendario e gli eventi creati per le prenotazioni (con nome e numero del cliente).
          </p>
          <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
            Il servizio non è pensato per trattare dati sulla salute o altre categorie particolari
            di dati (art. 9 GDPR). Ti chiediamo di non inviarli in chat: per richieste di questo tipo
            chiedi di parlare con una persona dell&apos;attività.
          </p>
        </Section>

        <Section title="3. Perché li trattiamo e su quale base giuridica">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              Rispondere alle tue richieste, proporti gli orari disponibili e gestire la
              prenotazione, anche passando la conversazione a una persona dell&apos;attività:
              esecuzione di un contratto o di misure precontrattuali richieste da te (art. 6.1.b
              GDPR).
            </li>
            <li>
              Fornire la dashboard e gli account alle attività: esecuzione del contratto con
              l&apos;attività (art. 6.1.b GDPR).
            </li>
            <li>
              Sicurezza del servizio, prevenzione di abusi e frodi, registri tecnici: legittimo
              interesse (art. 6.1.f GDPR).
            </li>
            <li>Adempimento di obblighi di legge, se presenti (art. 6.1.c GDPR).</li>
          </ul>
          <p>
            I dati non sono usati per marketing, non sono venduti e non sono usati per profilazione
            pubblicitaria.
          </p>
        </Section>

        <Section title="4. Uso dell'intelligenza artificiale">
          <p>
            Le risposte su WhatsApp sono generate da un assistente automatico: te lo segnaliamo nel
            primo messaggio, come previsto dall&apos;art. 50 del Regolamento (UE) 2024/1689
            (&quot;AI Act&quot;). Un modello di intelligenza artificiale legge il testo dei tuoi
            messaggi solo per capire cosa chiedi (servizio, giorno, orario). Gli orari proposti e le
            conferme sono calcolati dal sistema sulla base del calendario reale
            dell&apos;attività, non inventati dall&apos;intelligenza artificiale.
          </p>
          <p>
            Non vengono prese decisioni basate unicamente su un trattamento automatizzato che
            producano effetti giuridici o che ti riguardino in modo significativo (art. 22 GDPR). In
            qualsiasi momento puoi chiedere di parlare con una persona: la conversazione passa
            all&apos;attività e l&apos;assistente smette di rispondere. I tuoi messaggi non sono
            usati per addestrare modelli di intelligenza artificiale.
          </p>
        </Section>

        <Section title="5. A chi comunichiamo i dati">
          <p>
            I dati sono accessibili all&apos;attività a cui scrivi e, per il funzionamento tecnico
            del servizio, ai seguenti fornitori, che agiscono come sub-responsabili del trattamento:
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Meta Platforms Ireland Ltd.</strong> (WhatsApp Business Platform): invio e
              ricezione dei messaggi.
            </li>
            <li>
              <strong>Groq, Inc.</strong> (Stati Uniti): elaborazione del testo dei messaggi da
              parte del modello di intelligenza artificiale.
            </li>
            <li>
              <strong>Supabase, Inc.</strong>: database e autenticazione degli account.
            </li>
            <li>
              <strong>Render Services, Inc.</strong>: hosting del server che elabora i messaggi.
            </li>
            <li>
              <strong>Vercel Inc.</strong>: hosting della dashboard.
            </li>
            <li>
              <strong>Google</strong> (Google Calendar): solo se l&apos;attività collega il proprio
              calendario, per verificare la disponibilità e registrare l&apos;appuntamento.
            </li>
          </ul>
          <p>
            I dati non sono diffusi. Possono essere comunicati alle autorità solo se previsto dalla
            legge.
          </p>
        </Section>

        <Section title="6. Trasferimenti fuori dall'Unione europea">
          <p>
            Alcuni fornitori hanno sede o server negli Stati Uniti. In questi casi il trasferimento
            avviene sulla base della decisione di adeguatezza della Commissione europea relativa
            all&apos;EU-U.S. Data Privacy Framework, per i fornitori che vi aderiscono, oppure delle
            Clausole contrattuali standard approvate dalla Commissione (art. 46 GDPR).
          </p>
        </Section>

        <Section title="7. Per quanto tempo conserviamo i dati">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              Conversazioni e prenotazioni: per il tempo in cui l&apos;attività utilizza il
              servizio. Sono cancellate su tua richiesta (vedi punto 10) o entro 30 giorni dalla
              chiusura dell&apos;account dell&apos;attività.
            </li>
            <li>
              Dati dell&apos;account: per la durata dell&apos;account; cancellati entro 30 giorni
              dalla sua chiusura.
            </li>
            <li>
              Collegamento a Google Calendar: il token viene cancellato subito quando
              l&apos;attività scollega il calendario.
            </li>
          </ul>
        </Section>

        <Section title="8. Come proteggiamo i dati">
          <p>
            Tutte le comunicazioni sono cifrate (HTTPS). I messaggi in arrivo da WhatsApp sono
            accettati solo se firmati da Meta. I dati di ogni attività sono separati a livello di
            database e sono accessibili solo agli utenti di quell&apos;attività. I token di accesso a
            Google Calendar sono conservati cifrati.
          </p>
        </Section>

        <Section title="9. I tuoi diritti">
          <p>
            Puoi chiedere in ogni momento l&apos;accesso ai tuoi dati, la rettifica, la
            cancellazione, la limitazione del trattamento, la portabilità e opporti al trattamento
            (artt. 15-22 GDPR). Se sei un cliente di un&apos;attività, puoi rivolgerti direttamente
            all&apos;attività oppure scrivere a <Mail />: inoltreremo la richiesta all&apos;attività
            e la aiuteremo a risponderti.
          </p>
          <p>
            Hai anche il diritto di proporre reclamo al Garante per la protezione dei dati personali
            (Piazza Venezia 11, 00187 Roma,{" "}
            <a
              className="font-medium text-emerald-700 underline"
              href="https://www.garanteprivacy.it"
              rel="noopener noreferrer"
              target="_blank"
            >
              www.garanteprivacy.it
            </a>
            ).
          </p>
        </Section>

        <Section title="10. Come chiedere la cancellazione dei dati">
          <p>
            Scrivi a <Mail /> indicando il numero di telefono con cui hai scritto su WhatsApp e il
            nome dell&apos;attività. Cancelliamo conversazioni, messaggi e prenotazioni collegati a
            quel numero entro 30 giorni e ti confermiamo l&apos;avvenuta cancellazione. Per
            l&apos;eliminazione di un account di un&apos;attività scrivi dallo stesso indirizzo
            email dell&apos;account.
          </p>
          <p>
            Per non ricevere più messaggi puoi anche smettere di scrivere o bloccare il numero
            dell&apos;attività su WhatsApp. I dati trattati da WhatsApp come piattaforma restano
            regolati dall&apos;informativa di WhatsApp.
          </p>
        </Section>

        <Section title="11. Cookie">
          <p>
            La dashboard usa solo cookie tecnici necessari per mantenere l&apos;accesso
            all&apos;account. Non usiamo cookie di profilazione né strumenti di analisi di terze
            parti, quindi non è richiesto il consenso (Linee guida del Garante sui cookie del 10
            giugno 2021).
          </p>
        </Section>

        <Section title="12. Modifiche">
          <p>
            Possiamo aggiornare questa informativa. La data dell&apos;ultimo aggiornamento è
            indicata in alto.
          </p>
        </Section>
      </div>
    </main>
  );
}
