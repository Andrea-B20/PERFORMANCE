# Come funziona

Ogni mattina alle 08:00 il Mac scarica i dati da Garmin, ricalcola l'analisi,
cifra tutto e pubblica il sito. Tu apri la pagina e inserisci la passphrase.

---

## Perché la sincronizzazione gira sul Mac e non su GitHub

Il primo tentativo usava GitHub Actions, ma non poteva funzionare.

Il token Garmin è in realtà una coppia: uno di lunga durata (OAuth1) e uno
di sessione (OAuth2) che vale circa un'ora. A ogni esecuzione la libreria
deve riscambiare il primo per ottenere il secondo, e **quell'endpoint è
protetto contro il traffico automatizzato**: dai server di GitHub risponde
con un corpo non-JSON, quindi lo scambio fallisce sempre.

Non era un problema di token o di configurazione: non funzionerebbe con
nessun token. Dal tuo Mac, con il tuo indirizzo IP, lo stesso identico
token funziona senza problemi.

Conseguenza pratica: **il report si aggiorna solo se il Mac si accende in
giornata.** Se resta spento, al risveglio successivo launchd recupera
l'esecuzione mancata e il report si allinea.

---

## L'unico passaggio che resta da fare

**Settings → Pages → Source: "Deploy from a branch" → Branch: `main` → Cartella: `/docs`** → Save

<https://github.com/Andrea-B20/PERFORMANCE/settings/pages>

Dopo un paio di minuti il sito è online:
**<https://andrea-b20.github.io/PERFORMANCE/>**

---

## Il giro quotidiano

Il job `com.andrea.trainingcoach` è già installato e attivo. Ogni mattina:

1. scarica gli ultimi dati da Garmin
2. ricalcola analisi, rilievi e confronto con la settimana precedente
3. cifra tutto con AES-256-GCM
4. fa commit e push di `docs/index.html`

I dati grezzi restano in `data/`, escluso da git. Nel repository finisce solo
il file cifrato.

Per lanciarlo a mano quando vuoi:

```bash
cd "/Users/andreabracci/TRAINING COACH" && ./publish.sh
```

---

## La passphrase

Sta nel Portachiavi di macOS, non su disco. Per cambiarla:

```bash
security add-generic-password -a "$USER" -s TRAINING_COACH_PASSPHRASE -w -U
```

Poi rilancia `./publish.sh`: il sito viene ricifrato con quella nuova.

Se la dimentichi non è recuperabile, ma basta cambiarla così: i dati vengono
rigenerati da Garmin a ogni giro, quindi non si perde niente.

---

## Il token Garmin

Vale circa un anno. Quando scade, `publish.sh` fallisce con un messaggio
esplicito. Per rigenerarlo basta rifare il login:

```bash
cd "/Users/andreabracci/TRAINING COACH" && source venv/bin/activate && python scripts/fetch_data.py --days 7
```

Ti chiederà email e password una volta sola e riscriverà il token in
`~/.garminconnect`.

---

## Se qualcosa non va

Il registro di ogni esecuzione è in `logs/publish.log`:

```bash
tail -40 "/Users/andreabracci/TRAINING COACH/logs/publish.log"
```

**La pagina dice "passphrase errata" ma è giusta** — stai aprendo il file da
`file://`. La decifratura richiede una connessione sicura: usa l'indirizzo
`https://andrea-b20.github.io/PERFORMANCE/`.

**Il report è fermo a ieri** — il Mac non si è acceso, oppure l'orologio non
aveva sincronizzato. Lancia `./publish.sh` a mano.

**Voglio disattivare l'aggiornamento automatico:**

```bash
launchctl unload ~/Library/LaunchAgents/com.andrea.trainingcoach.plist
```

Per riattivarlo, `load` al posto di `unload`.

---

## Vedere il sito in locale senza pubblicarlo

```bash
cd "/Users/andreabracci/TRAINING COACH" && python3 -m http.server 8787 --directory docs
```

Poi <http://localhost:8787> (serve `localhost`, non `file://`).
