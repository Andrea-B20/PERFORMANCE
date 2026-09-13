# Pubblicazione del sito — istruzioni

Tre passaggi, una volta sola. Dopo, il report si aggiorna da solo ogni mattina.

---

## 1. Crea il repository e caricalo

Il repository è <https://github.com/Andrea-B20/PERFORMANCE>.

> **Deve essere pubblico** se hai un piano GitHub gratuito: Pages non funziona su
> repository privati senza abbonamento. Non è un problema — nel repository finiscono
> solo gli script, mai i dati: `data/`, `site/`, `report.html` e `dashboard.html`
> sono esclusi da `.gitignore`, e l'unico file pubblicato contiene i dati **cifrati**.

Dalla cartella del progetto:

```bash
cd "/Users/andreabracci/TRAINING COACH" && git init && git add . && git status
```

Controlla che nell'elenco **non** compaiano `data/`, `site/`, `report.html`,
`dashboard.html` o `garmin_token.txt`. Poi:

```bash
cd "/Users/andreabracci/TRAINING COACH" && git commit -m "Report allenamento automatizzato" && git branch -M main
```

```bash
cd "/Users/andreabracci/TRAINING COACH" && git remote add origin https://github.com/Andrea-B20/PERFORMANCE.git && git push -u origin main
```

---

## 2. Imposta i due secret

Sul repository: **Settings → Secrets and variables → Actions → New repository secret**.

### `GARMIN_TOKEN`

Genera il token e mandalo negli appunti (non viene mai mostrato a schermo):

```bash
cd "/Users/andreabracci/TRAINING COACH" && source venv/bin/activate && python scripts/export_token.py
```

Incolla il contenuto degli appunti nel secret chiamato `GARMIN_TOKEN`.

Vale circa un anno, poi va rigenerato con lo stesso comando. Se il workflow inizia
a fallire con errori di autenticazione, è questo il motivo.

### `SITE_PASSPHRASE`

La passphrase con cui sbloccherai il sito. Scegline una lunga e sceglila bene:

- **non è recuperabile** — non esiste un "password dimenticata"
- se la perdi, basta cambiare il secret: al giro successivo il sito è ricifrato con la nuova
- usane una diversa da quelle che usi altrove, e salvala nel tuo gestore di password

---

## 3. Attiva Pages e fai il primo giro

**Settings → Pages → Source: GitHub Actions** (non "Deploy from a branch").

Poi **Actions → Report giornaliero → Run workflow** per lanciarlo subito.

Il primo giro dura qualche minuto (scarica 180 giorni). Quelli successivi durano
meno di un minuto, perché i dati già scaricati restano nella cache di Actions.

Al termine il sito è su `https://andrea-b20.github.io/PERFORMANCE/`.

---

## Come funziona ogni giorno

Alle **08:10** e alle **12:10** italiane (due passaggi, così se sincronizzi l'orologio
tardi il report si aggiorna comunque):

1. Actions scarica gli ultimi dati da Garmin con il token
2. Ricalcola analisi, rilievi e confronto con la settimana precedente
3. Cifra tutto con AES-256-GCM usando la passphrase
4. Pubblica la pagina su GitHub Pages

I dati grezzi restano nella cache di Actions e sul tuo Mac. Nel repository non
entrano mai. Sul sito pubblicato c'è solo il blob cifrato.

---

## Cosa vedi la mattina

In cima: **prontezza di oggi** e l'indicazione operativa (riposo / facile / media /
via libera). Sotto: **"Sto migliorando?"**, il confronto fra gli ultimi 7 giorni e i
7 precedenti su dieci indicatori — è la sezione che risponde alla domanda nel tempo.

---

## Comandi utili

Aggiornare tutto in locale (dashboard + referto):

```bash
cd "/Users/andreabracci/TRAINING COACH" && ./update_dashboard.sh
```

Vedere il sito cifrato in locale prima di pubblicarlo — serve `localhost`, perché la
decifratura del browser richiede una connessione sicura e da `file://` non funziona:

```bash
cd "/Users/andreabracci/TRAINING COACH" && source venv/bin/activate && SITE_PASSPHRASE="la-tua-passphrase" python scripts/build_site.py && python3 -m http.server 8787 --directory site
```

Poi apri <http://localhost:8787>.

---

## Se qualcosa non va

**Il workflow fallisce sull'autenticazione** — il token è scaduto: rigeneralo con
`export_token.py` e aggiorna il secret.

**La pagina dice "passphrase errata" ma è giusta** — stai aprendo il file da
`file://`. Serve `https://` (GitHub Pages) o `http://localhost`.

**Il report mostra dati vecchi** — l'orologio non aveva ancora sincronizzato al
momento del giro. Il passaggio delle 12:10 dovrebbe recuperare; in alternativa
lancia il workflow a mano da Actions.

**Voglio togliere tutto** — cancella il repository: i dati restano solo sul tuo Mac.
