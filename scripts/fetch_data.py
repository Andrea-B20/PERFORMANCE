"""Scarica i dati da Garmin Connect e li salva localmente come JSON.

Uso:
    python scripts/fetch_data.py [--days 90] [--force]

I dati vengono salvati in data/raw/. Le chiamate per-giorno vengono
saltate se il file esiste già (usa --force per riscaricare tutto).
Nessun dato lascia questo computer.
"""
import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garmin_auth import get_client

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def save_json(name: str, payload) -> None:
    path = RAW_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def load_existing(name: str) -> list:
    path = RAW_DIR / name
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_daily(client, days: int, force: bool, refresh_days: int = 3) -> None:
    """I giorni più recenti vengono riscaricati sempre: quando li si legge la
    mattina i dati della notte possono essere ancora parziali o non sincronizzati."""
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=i)
        d_str = d.isoformat()
        refetch = force or i < refresh_days

        stats_path = RAW_DIR / f"{d_str}_stats.json"
        if refetch or not stats_path.exists():
            try:
                stats = client.get_stats(d_str)
                save_json(f"{d_str}_stats.json", stats)
            except Exception as e:
                print(f"  [stats] {d_str}: errore ({e})")
            time.sleep(0.2)

        sleep_path = RAW_DIR / f"{d_str}_sleep.json"
        if refetch or not sleep_path.exists():
            try:
                sleep = client.get_sleep_data(d_str)
                save_json(f"{d_str}_sleep.json", sleep)
            except Exception as e:
                print(f"  [sleep] {d_str}: errore ({e})")
            time.sleep(0.2)

        for kind, method in (
            ("hrv", client.get_hrv_data),
            ("readiness", client.get_training_readiness),
            ("trainingstatus", client.get_training_status),
            ("maxmetrics", client.get_max_metrics),
        ):
            path = RAW_DIR / f"{d_str}_{kind}.json"
            if refetch or not path.exists():
                try:
                    save_json(f"{d_str}_{kind}.json", method(d_str))
                except Exception as e:
                    print(f"  [{kind}] {d_str}: errore ({e})")
                time.sleep(0.2)

        if i % 10 == 0:
            print(f"  giorno {i + 1}/{days} ({d_str})...")


def fetch_range_data(client, days: int) -> None:
    today = date.today()
    start = (today - timedelta(days=days)).isoformat()
    end = today.isoformat()

    print("  attività...")
    try:
        activities = client.get_activities_by_date(start, end)
        # Unione con lo storico: un fetch su intervallo breve non deve cancellare
        # le attività più vecchie già scaricate.
        existing = load_existing("activities.json")
        merged = {a["activityId"]: a for a in existing if a.get("activityId")}
        merged.update({a["activityId"]: a for a in activities if a.get("activityId")})
        out = sorted(merged.values(), key=lambda a: a.get("startTimeLocal") or "", reverse=True)
        save_json("activities.json", out)
        print(f"    {len(activities)} scaricate, {len(out)} totali in archivio")
    except Exception as e:
        print(f"  [activities] errore ({e})")

    print("  body battery...")
    try:
        body_battery = []
        chunk_start = today - timedelta(days=days)
        while chunk_start <= today:
            chunk_end = min(chunk_start + timedelta(days=27), today)
            body_battery += client.get_body_battery(chunk_start.isoformat(), chunk_end.isoformat())
            chunk_start = chunk_end + timedelta(days=1)
            time.sleep(0.2)
        merged = {b["date"]: b for b in load_existing("body_battery.json") if b.get("date")}
        merged.update({b["date"]: b for b in body_battery if b.get("date")})
        save_json("body_battery.json", sorted(merged.values(), key=lambda b: b["date"]))
    except Exception as e:
        print(f"  [body_battery] errore ({e})")

    print("  composizione corporea...")
    try:
        body_comp = client.get_body_composition(start, end)
        save_json("body_composition.json", body_comp)
    except Exception as e:
        print(f"  [body_composition] errore ({e})")

    print("  pesate...")
    try:
        weigh_ins = client.get_weigh_ins(start, end)
        save_json("weigh_ins.json", weigh_ins)
    except Exception as e:
        print(f"  [weigh_ins] errore ({e})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="Quanti giorni indietro scaricare")
    parser.add_argument("--force", action="store_true", help="Riscarica anche i giorni già in cache")
    parser.add_argument("--refresh-days", type=int, default=3,
                        help="Giorni recenti da riscaricare sempre (dati ancora parziali)")
    args = parser.parse_args()

    print("Login a Garmin Connect...")
    client = get_client()

    print(f"Scarico dati giornalieri per gli ultimi {args.days} giorni...")
    fetch_daily(client, args.days, args.force, args.refresh_days)

    print("Scarico dati per intervallo (attività, body battery, peso)...")
    fetch_range_data(client, args.days)

    print("Fatto. Dati salvati in", RAW_DIR)


if __name__ == "__main__":
    main()
