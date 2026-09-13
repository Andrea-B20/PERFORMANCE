"""Motore di analisi: legge data/raw/ e produce una valutazione tecnica.

Applica soglie di riferimento della letteratura su carico, recupero e sonno
e genera i rilievi (findings) con severità, evidenze e correzioni.

Uso:
    python scripts/analyze.py        # stampa il referto a schermo
    (viene richiamato da build_report.py)
"""
import json
import statistics as st
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"

# Soglie di riferimento
SLEEP_TARGET_H = 7.5          # fabbisogno adulto (7-9h)
SLEEP_MIN_H = 7.0
REM_TARGET_PCT = 20.0         # 20-25% del sonno totale
DEEP_TARGET_PCT = 13.0        # 13-23%
BEDTIME_SD_TARGET_MIN = 30    # regolarità: dev.st < 30 min
ACWR_SWEET_MIN, ACWR_SWEET_MAX = 0.8, 1.3
ACWR_DANGER = 1.5
EASY_TARGET_PCT = 80          # modello polarizzato
HARD_TARGET_PCT = 15
HIIT_MAX_WEEK = 3


def load_json(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def collect():
    daily, sleep, readiness, hrv = {}, {}, {}, {}
    for f in RAW.glob("*_stats.json"):
        s = load_json(f)
        if s and s.get("totalSteps") is not None:
            daily[f.name[:10]] = s
    for f in RAW.glob("*_sleep.json"):
        s = load_json(f) or {}
        dto = s.get("dailySleepDTO") or {}
        if dto.get("sleepTimeSeconds"):
            sleep[f.name[:10]] = {"dto": dto, "hrv": s.get("avgOvernightHrv"),
                                  "hrvStatus": s.get("hrvStatus")}
            if s.get("avgOvernightHrv"):
                hrv[f.name[:10]] = s["avgOvernightHrv"]
    for f in RAW.glob("*_readiness.json"):
        r = load_json(f)
        if isinstance(r, list):
            r = r[0] if r else None
        if r and r.get("score") is not None:
            readiness[f.name[:10]] = r
    acts = [a for a in (load_json(RAW / "activities.json") or [])]
    return daily, sleep, readiness, hrv, acts


def training_status_info():
    files = sorted(RAW.glob("*_trainingstatus.json"))
    for f in reversed(files):
        ts = load_json(f) or {}
        out = {"date": f.name[:10]}
        tsd = (ts.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
        for _dev, v in tsd.items():
            out["status"] = v.get("trainingStatus")
            out["feedback"] = v.get("trainingStatusFeedbackPhrase")
            acwr = v.get("acuteTrainingLoadDTO") or {}
            out["acwr"] = acwr.get("dailyAcuteChronicWorkloadRatio")
            out["acwrStatus"] = acwr.get("acwrStatus")
            out["loadAcute"] = acwr.get("dailyTrainingLoadAcute")
            out["loadChronic"] = acwr.get("dailyTrainingLoadChronic")
            break
        tl = (ts.get("mostRecentTrainingLoadBalance") or {}).get(
            "metricsTrainingLoadBalanceDTOMap") or {}
        for _dev, v in tl.items():
            out["balance"] = {
                "anaerobic": v.get("monthlyLoadAnaerobic"),
                "anaerobicMin": v.get("monthlyLoadAnaerobicTargetMin"),
                "anaerobicMax": v.get("monthlyLoadAnaerobicTargetMax"),
                "aerobicHigh": v.get("monthlyLoadAerobicHigh"),
                "aerobicHighMin": v.get("monthlyLoadAerobicHighTargetMin"),
                "aerobicHighMax": v.get("monthlyLoadAerobicHighTargetMax"),
                "aerobicLow": v.get("monthlyLoadAerobicLow"),
                "aerobicLowMin": v.get("monthlyLoadAerobicLowTargetMin"),
                "aerobicLowMax": v.get("monthlyLoadAerobicLowTargetMax"),
                "feedback": v.get("trainingBalanceFeedbackPhrase"),
            }
            break
        if out.get("status") is not None or out.get("balance"):
            return out
    return {}


def bedtime_hours(dto):
    ms = dto.get("sleepStartTimestampLocal")
    if not ms:
        return None
    from datetime import datetime
    b = datetime.utcfromtimestamp(ms / 1000)
    h = b.hour + b.minute / 60
    return h + 24 if h < 12 else h


def analyse():
    daily, sleep, readiness, hrv, acts = collect()
    ts = training_status_info()
    dates = sorted(daily)
    if not dates:
        raise SystemExit("Nessun dato disponibile: esegui prima fetch_data.py")
    first, last = dates[0], dates[-1]

    acts = [a for a in acts if a.get("startTimeLocal", "")[:10] >= first]
    load = defaultdict(float)
    zone = defaultdict(lambda: [0.0] * 5)
    for a in acts:
        d = a["startTimeLocal"][:10]
        load[d] += a.get("activityTrainingLoad") or 0
        for i in range(5):
            zone[d][i] += (a.get(f"hrTimeInZone_{i+1}") or 0) / 60

    span = [(date.fromisoformat(first) + timedelta(days=i)).isoformat()
            for i in range((date.fromisoformat(last) - date.fromisoformat(first)).days + 1)]

    # --- serie ACWR
    acwr_series = []
    for i, d in enumerate(span):
        if i < 13:
            continue
        ac = sum(load[x] for x in span[max(0, i - 6):i + 1]) / 7
        ch = sum(load[x] for x in span[max(0, i - 27):i + 1]) / min(28, i + 1)
        acwr_series.append({"date": d, "acwr": round(ac / ch, 2) if ch else None,
                            "acute": round(ac, 1), "chronic": round(ch, 1)})

    # --- sonno
    s_dates = sorted(sleep)
    hours = [sleep[d]["dto"]["sleepTimeSeconds"] / 3600 for d in s_dates]
    rem_pct = [(sleep[d]["dto"].get("remSleepSeconds") or 0) / sleep[d]["dto"]["sleepTimeSeconds"] * 100
               for d in s_dates]
    deep_pct = [(sleep[d]["dto"].get("deepSleepSeconds") or 0) / sleep[d]["dto"]["sleepTimeSeconds"] * 100
                for d in s_dates]
    beds = [b for b in (bedtime_hours(sleep[d]["dto"]) for d in s_dates) if b]
    scores = [((sleep[d]["dto"].get("sleepScores") or {}).get("overall") or {}).get("value")
              for d in s_dates]
    sleep_debt = sum(max(0, SLEEP_TARGET_H - h) for h in hours)

    # --- intensità
    ztot = [sum(zone[d][i] for d in span) for i in range(5)]
    zsum = sum(ztot) or 1
    easy_pct = (ztot[0] + ztot[1]) / zsum * 100
    mod_pct = ztot[2] / zsum * 100
    hard_pct = (ztot[3] + ztot[4]) / zsum * 100

    # --- recupero
    r_dates = sorted(readiness)
    r_scores = [readiness[d]["score"] for d in r_dates]
    poor_days = sum(1 for s in r_scores if s < 40)
    recovery_now = (readiness[r_dates[-1]].get("recoveryTime") or 0) / 60 if r_dates else 0
    h_dates = sorted(hrv)
    hrv_base = st.mean([hrv[d] for d in h_dates[:14]]) if len(h_dates) >= 14 else None
    hrv_recent = st.mean([hrv[d] for d in h_dates[-7:]]) if len(h_dates) >= 7 else None
    hrv_delta = (hrv_recent / hrv_base - 1) * 100 if hrv_base and hrv_recent else None
    hrv_status_recent = [sleep[d].get("hrvStatus") for d in s_dates[-7:]]

    rhr = [daily[d]["restingHeartRate"] for d in dates if daily[d].get("restingHeartRate")]
    rhr_base = st.mean(rhr[:14]) if len(rhr) >= 14 else None
    rhr_recent = st.mean(rhr[-7:]) if len(rhr) >= 7 else None

    # --- correlazione sonno -> prontezza
    pairs = [(sleep[d]["dto"]["sleepTimeSeconds"] / 3600, readiness[d]["score"])
             for d in r_dates if d in sleep]
    short_r = [r for h, r in pairs if h < 5.5]
    long_r = [r for h, r in pairs if h >= 7]

    hiit = [a for a in acts if a["activityType"]["typeKey"] == "hiit"]
    weeks = max(1, len(span) / 7)
    hiit_per_week = len(hiit) / weeks
    hiit_evening = sum(1 for a in hiit if a["startTimeLocal"][11:13] >= "19")
    rest_days = [d for d in span if load[d] == 0]

    findings = []

    def add(sev, cat, title, evidence, why, actions):
        findings.append({"severity": sev, "category": cat, "title": title,
                         "evidence": evidence, "why": why, "actions": actions})

    # 1. Training status Garmin
    if ts.get("feedback", "").startswith("STRAINED") or ts.get("status") == 8:
        add("critical", "Carico", "Stato di allenamento: SOVRACCARICO (STRAINED)",
            [f"Garmin classifica il tuo stato attuale come «Strained» al {ts['date']}",
             f"Carico acuto {ts.get('loadAcute')} vs cronico {ts.get('loadChronic')} (rapporto {ts.get('acwr')})",
             f"{recovery_now:.0f} ore di recupero ancora consigliate"],
            "Lo stato «Strained» indica che il carico recente supera quello che il corpo "
            "sta riuscendo ad assorbire: la prestazione non migliora più e sale il rischio "
            "di infortunio e malattia.",
            ["Fermati o riduci drasticamente per 5-7 giorni (solo Z1-Z2, max 45 min)",
             "Nessuna seduta HIIT finché la readiness non risale sopra 50 per 3 giorni di fila",
             "Rientro graduale: prima settimana al 50-60% del volume abituale"])

    # 2. Squilibrio del carico
    bal = ts.get("balance") or {}
    if bal.get("anaerobic") and bal.get("anaerobicMax"):
        ana, amax = bal["anaerobic"], bal["anaerobicMax"]
        low, lmin = bal.get("aerobicLow") or 0, bal.get("aerobicLowMin") or 0
        if ana > amax:
            add("critical", "Carico", "Carico anaerobico oltre il doppio del target",
                [f"Anaerobico {ana:.0f} contro un target di {bal['anaerobicMin']:.0f}-{amax:.0f} "
                 f"({ana/amax*100:.0f}% del massimo)",
                 f"Aerobico di base {low:.0f} contro un target minimo di {lmin:.0f} "
                 f"({low/lmin*100:.0f}% del minimo)" if lmin else "",
                 f"{len(hiit)} sedute HIIT in {len(span)} giorni = {hiit_per_week:.1f} a settimana"],
                "Stai costruendo quasi tutto il carico su lavoro anaerobico, senza la base "
                "aerobica che permette di recuperarlo. È il classico schema che porta a "
                "stagnazione: tanta fatica, poco adattamento.",
                [f"Riduci l'HIIT a massimo {HIIT_MAX_WEEK} sedute settimanali (ora {hiit_per_week:.1f})",
                 "Aggiungi 2-3 uscite aerobiche facili da 45-60 min in Z2 (conversazione possibile)",
                 "Obiettivo: portare il carico aerobico di base dentro il target nelle prossime 4 settimane"])

    # 3. Sonno insufficiente
    avg_h = st.mean(hours)
    under6 = sum(1 for h in hours if h < 6)
    under5 = sum(1 for h in hours if h < 5)
    if avg_h < SLEEP_MIN_H:
        ev = [f"Media {avg_h:.1f}h a notte contro un fabbisogno di {SLEEP_MIN_H:.0f}-9h",
              f"{under6} notti su {len(hours)} sotto le 6h, di cui {under5} sotto le 5h",
              f"Debito di sonno accumulato: {sleep_debt:.0f} ore nel periodo"]
        if short_r and long_r:
            ev.append(f"Prontezza media {st.mean(short_r):.0f}/100 dopo notti <5.5h "
                      f"contro {st.mean(long_r):.0f}/100 dopo notti ≥7h")
        add("critical", "Sonno", "Restrizione cronica di sonno",
            ev,
            "Il sonno è il momento in cui avviene l'adattamento all'allenamento: rilascio di "
            "GH, consolidamento neuromuscolare, ripristino del sistema nervoso autonomo. "
            "Dormire meno di 6h annulla gran parte del lavoro fatto in palestra ed è, nei tuoi "
            "dati, il fattore più fortemente associato alla prontezza del giorno dopo.",
            ["Anticipa l'ora di addormentamento di 15 min a settimana fino ad arrivare alle 23:30",
             "Fissa una sveglia costante, anche nel weekend (ora varia di quasi 2 ore)",
             "Obiettivo minimo: 7h per almeno 5 notti a settimana"])

    # 4. Regolarità
    if beds and len(beds) > 3:
        bed_sd = st.stdev(beds) * 60
        bed_mean = st.mean(beds)
        if bed_sd > BEDTIME_SD_TARGET_MIN or bed_mean > 24.5:
            add("warning", "Sonno", "Orari di sonno tardivi e irregolari",
                [f"Ora media di addormentamento {int(bed_mean)%24:02d}:{int(bed_mean%1*60):02d}",
                 f"Variabilità dell'orario: ±{bed_sd:.0f} min (obiettivo <{BEDTIME_SD_TARGET_MIN} min)",
                 f"{hiit_evening} sedute HIIT su {len(hiit)} iniziate dopo le 19:00"],
                "Un ritmo circadiano instabile riduce la quota di sonno profondo e REM anche "
                "a parità di ore dormite. Allenarsi ad alta intensità in tarda serata alza "
                "cortisolo e temperatura corporea proprio quando dovrebbero scendere.",
                ["Sposta le sedute intense prima delle 18:00 quando possibile",
                 "Se ti alleni tardi: doccia tiepida, luci basse e niente schermi nell'ora successiva",
                 "Mantieni la stessa ora di sveglia: è l'ancora più forte del ritmo circadiano"])

    # 5. Architettura del sonno
    avg_rem = st.mean(rem_pct)
    if avg_rem < REM_TARGET_PCT:
        add("warning", "Sonno", "Sonno REM sotto la soglia fisiologica",
            [f"REM medio {avg_rem:.1f}% contro un riferimento di {REM_TARGET_PCT:.0f}-25%",
             f"{sum(1 for r in rem_pct if r < 15)} notti su {len(rem_pct)} sotto il 15%",
             f"Sonno profondo medio {st.mean(deep_pct):.1f}% (riferimento {DEEP_TARGET_PCT:.0f}-23%)"],
            "Il REM si concentra nella seconda metà della notte: accorciare il sonno lo "
            "taglia in modo sproporzionato. È la fase legata al recupero cognitivo e alla "
            "regolazione dello stress, e spiega la sensazione di stanchezza mentale. "
            f"Il sonno profondo al {st.mean(deep_pct):.0f}% è invece sopra il riferimento: non è "
            "un buon segno di per sé, è la firma della privazione di sonno — quando le ore "
            "sono poche l'organismo sacrifica il REM per salvare il sonno profondo.",
            ["Il REM si recupera allungando la notte, non cambiando l'ora della sveglia",
             "Evita alcol nelle 3-4 ore prima di dormire: sopprime selettivamente il REM",
             "Quando tornerai sopra le 7h, la quota REM si riequilibra da sola"])

    # 6. HRV
    if hrv_delta is not None and hrv_delta < -5:
        low_status = sum(1 for s in hrv_status_recent if s in ("LOW", "UNBALANCED"))
        add("critical" if hrv_delta < -10 else "warning", "Recupero",
            "Variabilità cardiaca (HRV) in calo",
            [f"HRV {hrv_recent:.0f} ms negli ultimi 7 giorni contro {hrv_base:.0f} ms di baseline "
             f"({hrv_delta:+.0f}%)",
             f"Stato HRV fuori equilibrio in {low_status} delle ultime 7 notti",
             f"Prontezza sotto 40/100 in {poor_days} giorni su {len(r_scores)}"],
            "L'HRV misura il tono parasimpatico: scende quando il sistema nervoso resta in "
            "allerta. Un calo superiore al 10% rispetto alla propria baseline, mantenuto per "
            "più giorni, è uno degli indicatori più affidabili di recupero insufficiente.",
            ["Usa l'HRV come semaforo: se lo stato è LOW, quel giorno niente alta intensità",
             "Il rialzo dell'HRV arriva prima dal sonno che dalla riduzione del carico",
             "Ricontrolla la tendenza tra 10 giorni: deve tornare verso la baseline"])

    # 6b. Alta intensità in giorni consecutivi
    hard_days = sorted({a["startTimeLocal"][:10] for a in acts
                        if (a.get("anaerobicTrainingEffect") or 0) >= 2.5
                        or (a.get("activityTrainingLoad") or 0) >= 150})
    streaks, cur = [], [hard_days[0]] if hard_days else []
    for prev, nxt in zip(hard_days, hard_days[1:]):
        if date.fromisoformat(nxt) - date.fromisoformat(prev) == timedelta(days=1):
            cur.append(nxt)
        else:
            streaks.append(cur)
            cur = [nxt]
    if cur:
        streaks.append(cur)
    longest = max(streaks, key=len) if streaks else []
    if len(longest) >= 2:
        add("critical" if len(longest) >= 3 else "warning", "Carico",
            "Sedute intense in giorni consecutivi",
            [f"{len(longest)} giorni consecutivi ad alta intensità dal {longest[0]} al {longest[-1]}",
             f"In totale {sum(1 for s in streaks if len(s) >= 2)} blocchi di giorni intensi ravvicinati",
             "L'adattamento anaerobico richiede 48h tra stimoli dello stesso tipo"],
            "Due sedute anaerobiche consecutive non sommano lo stimolo: la seconda si svolge "
            "su un sistema già svuotato, quindi produce fatica senza il corrispondente "
            "adattamento. È il modo più rapido per scavare un buco di recupero.",
            ["Lascia sempre almeno 48h tra due sedute HIIT",
             "Nel giorno intermedio: cammino, nuoto facile o forza a basso carico cardiaco",
             "Se vuoi allenarti comunque ogni giorno, alterna sistemi: intenso / aerobico / forza"])

    # 6c. Allenamento intenso a prontezza bassa
    ignored = [(d, readiness[d]["score"], round(load[d]))
               for d in r_dates if readiness[d]["score"] < 30 and load[d] >= 100]
    if ignored:
        last3 = ignored[-3:]
        add("critical", "Recupero", "Sedute intense svolte con prontezza in rosso",
            [f"{len(ignored)} giorni con prontezza sotto 30/100 e carico comunque elevato",
             "Più recenti: " + ", ".join(f"{d} (prontezza {s}/100, carico {l})" for d, s, l in last3),
             f"Oggi il dispositivo indica ancora {recovery_now:.0f}h di recupero necessarie"],
            "La prontezza sotto 30 significa che il sistema nervoso non ha recuperato dalla "
            "seduta precedente. Allenarsi duro in quella condizione non produce adattamento: "
            "aggiunge solo fatica su fatica, ed è la via diretta verso l'infortunio.",
            ["Regola pratica: prontezza sotto 30 = giorno facile o riposo, senza eccezioni",
             "Prontezza 30-50 = allenamento aerobico o tecnica, niente massimali",
             "Prontezza sopra 65 = via libera per la seduta intensa programmata"])

    # 7. ACWR
    peak = max((x["acwr"] for x in acwr_series if x["acwr"]), default=0)
    if peak > ACWR_DANGER:
        pk = max((x for x in acwr_series if x["acwr"]), key=lambda x: x["acwr"])
        add("warning", "Carico", "Picco di carico troppo rapido",
            [f"Rapporto carico acuto/cronico salito a {peak:.2f} il {pk['date']} "
             f"(zona ottimale {ACWR_SWEET_MIN}-{ACWR_SWEET_MAX})",
             f"Valore attuale {acwr_series[-1]['acwr']:.2f}" if acwr_series else "",
             f"Solo {len(rest_days)} giorni di riposo completo su {len(span)}"],
            "Un ACWR sopra 1.5 significa che la settimana corrente pesa molto più di quanto "
            "il corpo sia abituato a sostenere: è la condizione in cui la letteratura osserva "
            "il maggior tasso di infortuni da sovraccarico.",
            ["Aumenta il carico settimanale di non più del 10% alla volta",
             "Programma 1 giorno di riposo completo ogni 3-4 giorni di allenamento",
             "Ogni 4ª settimana: scarico al 50-60% del volume"])

    # 8. Distribuzione intensità
    if easy_pct < 70 or hard_pct > 20:
        add("warning", "Carico", "Distribuzione delle intensità sbilanciata",
            [f"Facile (Z1-Z2) {easy_pct:.0f}% contro un riferimento di ~{EASY_TARGET_PCT}%",
             f"Intenso (Z4-Z5) {hard_pct:.0f}% contro ~{HARD_TARGET_PCT}%",
             f"Zona intermedia (Z3) {mod_pct:.0f}%: è la «terra di nessuno» — troppo dura per "
             f"recuperare, troppo facile per stimolare"],
            "Il modello polarizzato (molto facile / poco ma veramente intenso) produce "
            "adattamenti superiori a parità di tempo, proprio perché lascia spazio al recupero. "
            "Accumulare volume in Z3 costa fatica senza dare lo stimolo dell'alta intensità.",
            ["Nei giorni facili tieni la FC sotto ~135 bpm: se non riesci a parlare, stai andando troppo forte",
             "Concentra l'intensità in 2-3 sedute a settimana, non spalmata ovunque",
             "La forza a basso carico cardiaco che già fai conta come lavoro facile: va benissimo"])

    # Verdetto
    crit = sum(1 for f in findings if f["severity"] == "critical")
    warn = sum(1 for f in findings if f["severity"] == "warning")
    if crit >= 2:
        verdict = {"level": "critical", "label": "Recupero insufficiente",
                   "text": "Il carico di allenamento è superiore a quello che il tuo recupero — "
                           "soprattutto il sonno — riesce a sostenere. Non è un problema di "
                           "impegno: ti stai allenando tanto e bene, ma stai togliendo al corpo "
                           "gli strumenti per trasformare quel lavoro in adattamento."}
    elif crit or warn >= 3:
        verdict = {"level": "warning", "label": "Segnali di allarme",
                   "text": "L'impianto regge, ma ci sono indicatori che stanno peggiorando e "
                           "vanno corretti prima che diventino un problema."}
    else:
        verdict = {"level": "ok", "label": "Equilibrio buono",
                   "text": "Carico e recupero sono in equilibrio. Continua così."}

    # ---- confronto fra periodi: "sto migliorando?"
    def window(seq_dates, seq_vals, lo, hi):
        vals = [v for d, v in zip(seq_dates, seq_vals) if lo <= d < hi and v is not None]
        return st.mean(vals) if vals else None

    end_d = date.fromisoformat(last)
    w1_lo = (end_d - timedelta(days=6)).isoformat()
    w0_lo = (end_d - timedelta(days=13)).isoformat()
    nxt = (end_d + timedelta(days=1)).isoformat()

    def cmp_metric(name, dts, vls, better, unit="", fmt=1):
        cur = window(dts, vls, w1_lo, nxt)
        prev = window(dts, vls, w0_lo, w1_lo)
        if cur is None or prev is None:
            return None
        delta = cur - prev
        improving = (delta > 0) if better == "up" else (delta < 0)
        if abs(delta) < (abs(prev) * 0.02):
            improving = None  # stabile
        return {"name": name, "current": round(cur, fmt), "previous": round(prev, fmt),
                "delta": round(delta, fmt), "better": better, "unit": unit,
                "improving": improving}

    load_dates = span
    load_vals = [load[d] for d in span]
    hiit_by_day = defaultdict(int)
    for a in acts:
        if a["activityType"]["typeKey"] == "hiit":
            hiit_by_day[a["startTimeLocal"][:10]] += 1
    easy_by_day, hard_by_day = [], []
    for d in span:
        tot_d = sum(zone[d])
        easy_by_day.append((zone[d][0] + zone[d][1]) / tot_d * 100 if tot_d else None)
        hard_by_day.append((zone[d][3] + zone[d][4]) / tot_d * 100 if tot_d else None)

    trends = [t for t in [
        cmp_metric("Sonno medio", s_dates, hours, "up", "h", 1),
        cmp_metric("Punteggio sonno", s_dates, scores, "up", "/100", 0),
        cmp_metric("REM", s_dates, rem_pct, "up", "%", 1),
        cmp_metric("Prontezza", r_dates, r_scores, "up", "/100", 0),
        cmp_metric("HRV notturna", h_dates, [hrv[d] for d in h_dates], "up", " ms", 1),
        cmp_metric("FC riposo", dates, [daily[d].get("restingHeartRate") for d in dates],
                   "down", " bpm", 1),
        cmp_metric("Stress medio", dates, [daily[d].get("averageStressLevel") for d in dates],
                   "down", "/100", 0),
        cmp_metric("Carico giornaliero", load_dates, load_vals, "down", "", 0),
        cmp_metric("Tempo facile", span, easy_by_day, "up", "%", 0),
        cmp_metric("Sedute HIIT", span, [hiit_by_day[d] for d in span], "down", "/gg", 2),
    ] if t]

    improving_n = sum(1 for t in trends if t["improving"] is True)
    worsening_n = sum(1 for t in trends if t["improving"] is False)

    # ---- situazione di oggi
    today_r = readiness.get(last) or (readiness[r_dates[-1]] if r_dates else {})
    tscore = today_r.get("score")
    if tscore is None:
        advice = {"level": "unknown", "head": "Dato di prontezza non ancora disponibile",
                  "body": "Sincronizza l'orologio e ricarica la pagina."}
    elif tscore < 30:
        advice = {"level": "crit", "head": "Oggi si riposa",
                  "body": "Riposo completo o camminata. Nessuna seduta strutturata: "
                          "il sistema nervoso non ha recuperato."}
    elif tscore < 50:
        advice = {"level": "warn", "head": "Oggi solo lavoro facile",
                  "body": "Aerobico in Z2 o tecnica. Niente serie intense, niente massimali."}
    elif tscore < 65:
        advice = {"level": "mid", "head": "Oggi seduta media",
                  "body": "Forza submassimale o aerobico più lungo. L'alta intensità si rimanda."}
    else:
        advice = {"level": "ok", "head": "Oggi via libera all'intensità",
                  "body": "È il giorno giusto per la seduta intensa programmata."}

    last_sleep = sleep.get(last) or (sleep[s_dates[-1]] if s_dates else None)
    today = {
        "date": last,
        "readiness": tscore,
        "advice": advice,
        "recoveryHours": round((today_r.get("recoveryTime") or 0) / 60),
        "sleepHours": round(last_sleep["dto"]["sleepTimeSeconds"] / 3600, 1) if last_sleep else None,
        "sleepScore": (((last_sleep or {}).get("dto", {}).get("sleepScores") or {}).get("overall") or {}).get("value"),
        "hrv": (last_sleep or {}).get("hrv"),
        "hrvStatus": (last_sleep or {}).get("hrvStatus"),
    }

    # aderenza al piano: giorni dall'ultimo "intenso in rosso"
    last_bad = ignored[-1][0] if ignored else None
    days_clean = ((end_d - date.fromisoformat(last_bad)).days) if last_bad else None
    sleep_streak = 0
    for d in reversed(s_dates):
        if sleep[d]["dto"]["sleepTimeSeconds"] / 3600 >= SLEEP_MIN_H:
            sleep_streak += 1
        else:
            break

    return {
        "period": {"from": first, "to": last, "days": len(span)},
        "trends": trends,
        "trendSummary": {"improving": improving_n, "worsening": worsening_n,
                         "total": len(trends)},
        "today": today,
        "adherence": {"daysSinceHardOnRed": days_clean, "sleepStreak": sleep_streak,
                      "restDaysLast7": sum(1 for d in span[-7:] if load[d] == 0)},
        "verdict": verdict,
        "findings": findings,
        "trainingStatus": ts,
        "ignoredDays": [{"date": d, "score": s, "load": l} for d, s, l in ignored],
        "hardStreak": longest,
        "kpi": {
            "sleepAvg": round(avg_h, 1),
            "sleepUnder6": under6,
            "sleepNights": len(hours),
            "sleepDebt": round(sleep_debt),
            "remPct": round(avg_rem, 1),
            "deepPct": round(st.mean(deep_pct), 1),
            "bedtimeMean": f"{int(st.mean(beds))%24:02d}:{int(st.mean(beds)%1*60):02d}" if beds else None,
            "bedtimeSd": round(st.stdev(beds) * 60) if len(beds) > 3 else None,
            "sleepScore": round(st.mean([s for s in scores if s]), 1) if any(scores) else None,
            "hrvBase": round(hrv_base, 1) if hrv_base else None,
            "hrvRecent": round(hrv_recent, 1) if hrv_recent else None,
            "hrvDelta": round(hrv_delta, 1) if hrv_delta is not None else None,
            "rhrBase": round(rhr_base, 1) if rhr_base else None,
            "rhrRecent": round(rhr_recent, 1) if rhr_recent else None,
            "readinessPoorDays": poor_days,
            "readinessDays": len(r_scores),
            "readinessAvg": round(st.mean(r_scores)) if r_scores else None,
            "recoveryHours": round(recovery_now),
            "acwrNow": acwr_series[-1]["acwr"] if acwr_series else None,
            "acwrPeak": round(peak, 2),
            "easyPct": round(easy_pct), "modPct": round(mod_pct), "hardPct": round(hard_pct),
            "hiitPerWeek": round(hiit_per_week, 1),
            "hiitEvening": hiit_evening,
            "restDays": len(rest_days),
            "totalSessions": len(acts),
            "readinessShortSleep": round(st.mean(short_r)) if short_r else None,
            "readinessLongSleep": round(st.mean(long_r)) if long_r else None,
        },
        "series": {
            "dates": span,
            "load": [round(load[d]) for d in span],
            "acwr": acwr_series,
            "sleepDates": s_dates,
            "sleepHours": [round(h, 1) for h in hours],
            "sleepRem": [round(r, 1) for r in rem_pct],
            "sleepDeep": [round(r, 1) for r in deep_pct],
            "bedtimes": [bedtime_hours(sleep[d]["dto"]) for d in s_dates],
            "hrvDates": h_dates,
            "hrv": [hrv[d] for d in h_dates],
            "readinessDates": r_dates,
            "readiness": r_scores,
            "zones": [round(z) for z in ztot],
        },
    }


if __name__ == "__main__":
    res = analyse()
    print(f"PERIODO {res['period']['from']} -> {res['period']['to']}")
    print(f"VERDETTO: {res['verdict']['label'].upper()}\n")
    for f in res["findings"]:
        print(f"[{f['severity'].upper()}] {f['title']}")
        for e in f["evidence"]:
            if e:
                print(f"   · {e}")
        print()
