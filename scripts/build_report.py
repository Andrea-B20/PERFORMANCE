"""Genera report.html: il referto tecnico completo.

Uso:
    python scripts/build_report.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze import analyse

ROOT = Path(__file__).parent.parent
OUT = ROOT / "report.html"


def build_plan(k):
    """Piano di correzione parametrizzato sui valori reali."""
    return [
        {
            "cls": "p1",
            "when": "Giorni 1–7 · adesso",
            "title": "Scarico: interrompere l'accumulo",
            "items": [
                "<b>Zero sedute HIIT.</b> Nessuna eccezione, anche nei giorni in cui ti senti bene: "
                f"il dispositivo indica ancora {k['recoveryHours']}h di recupero da smaltire.",
                "Solo lavoro facile: camminata, nuoto tranquillo o bici in Z1–Z2, 30–45 min, "
                "a una frequenza che ti permetta di parlare.",
                "Forza: puoi mantenerla, ma al 60% dei carichi abituali e senza mai arrivare a cedimento. "
                "Le tue sedute di forza sono già a bassa frequenza cardiaca, quindi non sono il problema.",
                f"<b>Sonno: è questa la terapia.</b> Obiettivo 7h30 per almeno 5 notti su 7 "
                f"(ora sei a {k['sleepAvg']}h di media).",
                "Se compare voglia di allenarti duro, spostala: stai recuperando, non perdendo forma. "
                "La forma si esprime dopo lo scarico, non durante.",
            ],
            "exit": "prontezza sopra 50 per 3 giorni consecutivi <b>e</b> stato HRV tornato "
                    "«bilanciato». Se dopo 7 giorni non succede, prolunga di altri 3–4 giorni.",
        },
        {
            "cls": "p2",
            "when": "Settimane 2–5 · ricostruzione",
            "title": "Rimettere la base aerobica sotto l'intensità",
            "items": [
                f"HIIT: massimo 2 a settimana (ora {k['hiitPerWeek']}), <b>mai in giorni consecutivi</b>, "
                "e solo se la prontezza del mattino è sopra 65.",
                "Aggiungi 2–3 sedute aerobiche facili da 45–60 min: bici, corsa lenta o nuoto, "
                "tenendo la frequenza in Z2. È il lavoro che ti manca di più.",
                "Il volume totale può restare simile: stai spostando minuti dall'intenso al facile, "
                "non allenandoti di meno.",
                "Crescita del carico settimanale: non più del 10% alla volta.",
                "Un giorno di riposo completo a settimana, fisso in calendario.",
            ],
            "exit": "carico aerobico di base rientrato dentro la fascia target e ACWR stabilmente "
                    "tra 0,8 e 1,3 per due settimane di fila.",
        },
        {
            "cls": "p3",
            "when": "Dalla settimana 6 · mantenimento",
            "title": "Struttura sostenibile a lungo termine",
            "items": [
                "Distribuzione polarizzata stabile: ~80% del tempo facile, ~15% veramente intenso, "
                "il minimo possibile nella zona intermedia.",
                "Ogni 4ª settimana: scarico programmato al 50–60% del volume. "
                "Va messo in calendario prima, non deciso quando si è già stanchi.",
                "Le sedute intense si guadagnano con il recupero: se la prontezza non c'è, "
                "la seduta si sposta, non si salta l'ascolto del dato.",
                "Rileggi questo referto ogni 3–4 settimane rigenerandolo sui dati aggiornati: "
                "i numeri ti diranno se la correzione sta funzionando.",
            ],
            "exit": None,
        },
    ]


TRAFFIC = [
    {"range": "Sotto 30", "icon": "■", "color": "var(--crit)",
     "what": "Riposo completo o camminata. Nessun allenamento strutturato: il sistema nervoso "
             "non ha recuperato dalla seduta precedente."},
    {"range": "30 – 50", "icon": "■", "color": "var(--warn)",
     "what": "Solo lavoro aerobico facile o tecnica. Niente serie intense, niente massimali, "
             "durata contenuta."},
    {"range": "50 – 65", "icon": "■", "color": "var(--s4)",
     "what": "Seduta media: forza a carichi submassimali o aerobico più lungo. "
             "L'intensità alta si rimanda al giorno dopo."},
    {"range": "Sopra 65", "icon": "■", "color": "var(--good)",
     "what": "Via libera alla seduta intensa programmata. È il giorno in cui spendere "
             "la fatica dove rende davvero."},
]

WEEK = [
    {"d": "Lunedì", "s": "Forza (parte alta) + mobilità", "i": "Facile", "cls": "easy",
     "t": "50–60 min", "n": "Frequenza cardiaca bassa, come già fai ora"},
    {"d": "Martedì", "s": "HIIT", "i": "Intenso", "cls": "hard", "t": "35–45 min",
     "n": "Solo se prontezza &gt;65. Prima delle 18:00"},
    {"d": "Mercoledì", "s": "Aerobico facile (bici / corsa lenta / nuoto)", "i": "Facile",
     "cls": "easy", "t": "45–60 min", "n": "Zona 2: devi riuscire a parlare"},
    {"d": "Giovedì", "s": "Forza (parte bassa) + core", "i": "Facile", "cls": "easy",
     "t": "50–60 min", "n": "Recupero attivo tra i due stimoli intensi"},
    {"d": "Venerdì", "s": "HIIT", "i": "Intenso", "cls": "hard", "t": "35–45 min",
     "n": "72h dal precedente. Solo se prontezza &gt;65"},
    {"d": "Sabato", "s": "Aerobico lungo o tennis", "i": "Medio", "cls": "mid", "t": "60–75 min",
     "n": "Attività che ti piace, senza inseguire il ritmo"},
    {"d": "Domenica", "s": "Riposo completo", "i": "Riposo", "cls": "rest", "t": "—",
     "n": "Fisso in calendario, non negoziabile"},
]


def build_kpi_table(k):
    return [
        {"n": "Sonno medio per notte", "now": f"{k['sleepAvg']} h", "target": "≥ 7 h",
         "bad": k["sleepAvg"] < 7,
         "how": "È l'indicatore con più effetto su tutto il resto: nei tuoi dati vale "
                f"{(k['readinessLongSleep'] or 0) - (k['readinessShortSleep'] or 0)} punti di prontezza"},
        {"n": "Notti sotto le 6 ore", "now": f"{k['sleepUnder6']} su {k['sleepNights']}",
         "target": "≤ 1 a settimana", "bad": k["sleepUnder6"] > k["sleepNights"] * 0.15,
         "how": "Sotto le 6h il recupero notturno non compensa il carico del giorno"},
        {"n": "Ora media di addormentamento", "now": k["bedtimeMean"] or "—", "target": "≈ 23:30",
         "bad": True, "how": f"Variabilità attuale ±{k['bedtimeSd']} min: l'obiettivo è scendere sotto ±30"},
        {"n": "Quota di sonno REM", "now": f"{k['remPct']} %", "target": "20 – 25 %",
         "bad": k["remPct"] < 20,
         "how": "Si riequilibra da solo quando la durata totale sale: non serve agire direttamente"},
        {"n": "HRV notturna", "now": f"{k['hrvRecent']} ms", "target": f"≥ {k['hrvBase']} ms (baseline)",
         "bad": (k["hrvDelta"] or 0) < -5,
         "how": "Guarda la tendenza su 7 giorni, mai il singolo valore"},
        {"n": "Frequenza cardiaca a riposo", "now": f"{k['rhrRecent']} bpm",
         "target": f"≈ {k['rhrBase']} bpm", "bad": (k["rhrRecent"] or 0) > (k["rhrBase"] or 0) + 2,
         "how": "Un rialzo stabile di 3–5 bpm segnala stanchezza o inizio di malattia"},
        {"n": "Prontezza media", "now": f"{k['readinessAvg']}/100", "target": "> 55",
         "bad": (k["readinessAvg"] or 0) < 55,
         "how": f"Attualmente sotto 40 in {k['readinessPoorDays']} giorni su {k['readinessDays']}"},
        {"n": "ACWR (carico acuto/cronico)", "now": str(k["acwrNow"]), "target": "0,8 – 1,3",
         "bad": (k["acwrNow"] or 0) > 1.3,
         "how": "Sopra 1,5 il rischio di infortunio da sovraccarico cresce in modo netto"},
        {"n": "Sedute HIIT a settimana", "now": str(k["hiitPerWeek"]), "target": "≤ 2–3 ben distanziate",
         "bad": k["hiitPerWeek"] > 3,
         "how": "Conta più la distanza tra le sedute che il loro numero: servono 48h"},
        {"n": "Tempo facile (Z1–Z2)", "now": f"{k['easyPct']} %", "target": "≈ 80 %",
         "bad": k["easyPct"] < 70,
         "how": "È lo spazio che rende sostenibile l'intensità, non tempo sprecato"},
    ]


DISCLAIMER = (
    "<b>Come leggere questo referto.</b> L'analisi è costruita su dati di un dispositivo "
    "da polso: frequenza cardiaca, HRV e fasi del sonno sono stime, affidabili come tendenza "
    "ma non come misura clinica. Le indicazioni riguardano la gestione del carico di "
    "allenamento e dell'igiene del sonno, e non sostituiscono un parere medico. "
    "Se la stanchezza persiste nonostante lo scarico, o se compaiono altri sintomi — "
    "sonno non ristoratore prolungato, calo di peso involontario, infezioni ricorrenti, "
    "battito irregolare — vale la pena parlarne con un medico, perché HRV bassa e sonno "
    "frammentato possono avere anche cause non legate all'allenamento."
)


def main():
    res = analyse()
    k = res["kpi"]
    res["plan"] = build_plan(k)
    res["trafficLight"] = TRAFFIC
    res["week"] = WEEK
    res["kpiTable"] = build_kpi_table(k)
    res["disclaimer"] = DISCLAIMER
    res["generatedAt"] = datetime.now().isoformat(timespec="seconds")

    tpl = (Path(__file__).parent / "report_template.html").read_text()
    html = tpl.replace("__DATA_JSON__", json.dumps(res, ensure_ascii=False))
    OUT.write_text(html)

    crit = sum(1 for f in res["findings"] if f["severity"] == "critical")
    print(f"Referto generato: {OUT}")
    print(f"  Verdetto: {res['verdict']['label']}")
    print(f"  {len(res['findings'])} rilievi ({crit} critici)")


if __name__ == "__main__":
    main()
