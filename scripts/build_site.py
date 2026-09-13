"""Genera il sito cifrato in site/index.html.

La passphrase arriva da SITE_PASSPHRASE (variabile d'ambiente o GitHub Secret).
Nel file pubblicato finiscono SOLO dati cifrati: senza passphrase sono illeggibili.

Uso:
    SITE_PASSPHRASE="..." python scripts/build_site.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze import analyse
from build_report import TRAFFIC, WEEK, DISCLAIMER, build_plan, build_kpi_table
from crypto_payload import encrypt

ROOT = Path(__file__).parent.parent
SITE = ROOT / "docs"


def main():
    passphrase = os.environ.get("SITE_PASSPHRASE", "").strip()
    if not passphrase:
        sys.exit("SITE_PASSPHRASE non impostata: interrompo per non pubblicare dati in chiaro.")
    if len(passphrase) < 8:
        sys.exit("Passphrase troppo corta: usane una di almeno 8 caratteri.")

    res = analyse()
    k = res["kpi"]
    res["plan"] = build_plan(k)
    res["trafficLight"] = TRAFFIC
    res["week"] = WEEK
    res["kpiTable"] = build_kpi_table(k)
    res["disclaimer"] = DISCLAIMER
    res["generatedAt"] = datetime.now().isoformat(timespec="minutes")

    blob = encrypt(res, passphrase)

    tpl = (Path(__file__).parent / "site_template.html").read_text()
    html = tpl.replace("__ENCRYPTED_PAYLOAD__", json.dumps(blob))

    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html)
    (SITE / ".nojekyll").write_text("")

    # Verifica anti-fuga: nessun contenuto dell'analisi deve comparire in chiaro.
    # (I nomi di proprietà stanno nel codice JS del template, quindi si controllano
    #  i valori: testi dei rilievi, verdetto e date dei dati.)
    leaks = [res["verdict"]["text"][:40], res["period"]["from"], res["today"]["advice"]["head"]]
    leaks += [f["title"][:30] for f in res["findings"][:3]]
    for probe in leaks:
        if probe and probe in html:
            sys.exit(f"Dati in chiaro trovati nell'output ({probe!r}): interrompo.")
    if "__ENCRYPTED_PAYLOAD__" in html:
        sys.exit("Payload non sostituito nel template: interrompo.")

    size_kb = len(html.encode()) / 1024
    print(f"Sito generato: {SITE/'index.html'} ({size_kb:.0f} KB)")
    print(f"  Periodo {res['period']['from']} → {res['period']['to']}")
    print(f"  {len(res['findings'])} rilievi · payload cifrato AES-256-GCM")


if __name__ == "__main__":
    main()
