"""Aggrega i dati in data/raw/ e genera dashboard.html.

Uso:
    python scripts/build_dashboard.py

Non richiede login: legge solo i file JSON già scaricati da fetch_data.py.
"""
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = ROOT / "dashboard.html"

DAILY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(stats|sleep)\.json$")


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def collect_daily():
    stats_by_date = {}
    sleep_by_date = {}
    for f in RAW_DIR.glob("*.json"):
        m = DAILY_RE.match(f.name)
        if not m:
            continue
        d, kind = m.groups()
        data = load_json(f)
        if data is None:
            continue
        if kind == "stats":
            stats_by_date[d] = data
        else:
            sleep_by_date[d] = data
    return stats_by_date, sleep_by_date


def build_daily_series(stats_by_date, sleep_by_date, body_battery_list):
    bb_by_date = {b.get("date"): b for b in (body_battery_list or [])}
    dates = sorted(set(stats_by_date) | set(sleep_by_date) | set(bb_by_date))

    daily = []
    for d in dates:
        s = stats_by_date.get(d, {})
        sl = sleep_by_date.get(d, {})
        dto = sl.get("dailySleepDTO") or {}
        scores = dto.get("sleepScores") or {}
        overall = scores.get("overall") or {}
        bb = bb_by_date.get(d, {})

        daily.append({
            "date": d,
            "steps": s.get("totalSteps"),
            "stepGoal": s.get("dailyStepGoal"),
            "distanceKm": round(s["totalDistanceMeters"] / 1000, 2) if s.get("totalDistanceMeters") else None,
            "activeKcal": s.get("activeKilocalories"),
            "totalKcal": s.get("totalKilocalories"),
            "restingHR": s.get("restingHeartRate"),
            "avgStress": s.get("averageStressLevel"),
            "moderateMin": s.get("moderateIntensityMinutes"),
            "vigorousMin": s.get("vigorousIntensityMinutes"),
            "bbHighest": s.get("bodyBatteryHighestValue"),
            "bbLowest": s.get("bodyBatteryLowestValue"),
            "bbCharged": bb.get("charged", s.get("bodyBatteryChargedValue")),
            "bbDrained": bb.get("drained", s.get("bodyBatteryDrainedValue")),
            "avgSpo2": s.get("averageSpo2"),
            "sleepScore": overall.get("value"),
            "sleepSeconds": dto.get("sleepTimeSeconds"),
            "deepSeconds": dto.get("deepSleepSeconds"),
            "lightSeconds": dto.get("lightSleepSeconds"),
            "remSeconds": dto.get("remSleepSeconds"),
            "awakeSeconds": dto.get("awakeSleepSeconds"),
            "sleepAvgHR": dto.get("avgHeartRate"),
            "sleepAvgStress": dto.get("avgSleepStress"),
        })
    return daily


def build_activities(activities_raw):
    out = []
    for a in activities_raw or []:
        atype = (a.get("activityType") or {}).get("typeKey", "other")
        out.append({
            "id": a.get("activityId"),
            "name": a.get("activityName"),
            "type": atype,
            "date": (a.get("startTimeLocal") or "")[:10],
            "startTimeLocal": a.get("startTimeLocal"),
            "durationMin": round(a["duration"] / 60, 1) if a.get("duration") else None,
            "distanceKm": round(a["distance"] / 1000, 2) if a.get("distance") else None,
            "calories": a.get("calories"),
            "avgHR": a.get("averageHR"),
            "maxHR": a.get("maxHR"),
            "aerobicTE": a.get("aerobicTrainingEffect"),
            "anaerobicTE": a.get("anaerobicTrainingEffect"),
        })
    out.sort(key=lambda x: x["startTimeLocal"] or "", reverse=True)
    return out


def build_weight(weigh_ins_raw):
    out = []
    if not weigh_ins_raw:
        return out
    for entry in weigh_ins_raw.get("dailyWeightSummaries") or []:
        latest = entry.get("latestWeight") or {}
        weight_g = latest.get("weight")
        if weight_g is None:
            continue
        out.append({
            "date": entry.get("summaryDate"),
            "weightKg": round(weight_g / 1000, 1),
            "bodyFat": latest.get("bodyFat"),
            "bmi": latest.get("bmi"),
        })
    out.sort(key=lambda x: x["date"])
    return out


def safe_avg(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 1) if vals else None


def build_summary(daily, activities, weight):
    return {
        "days": len(daily),
        "avgSteps": (lambda v: round(v) if v is not None else None)(safe_avg([d["steps"] for d in daily])),
        "avgRestingHR": safe_avg([d["restingHR"] for d in daily]),
        "avgSleepScore": safe_avg([d["sleepScore"] for d in daily]),
        "avgSleepHours": safe_avg([d["sleepSeconds"] / 3600 if d["sleepSeconds"] else None for d in daily]),
        "avgStress": safe_avg([d["avgStress"] for d in daily]),
        "totalActivities": len(activities),
        "currentWeightKg": weight[-1]["weightKg"] if weight else None,
    }


def main():
    stats_by_date, sleep_by_date = collect_daily()
    activities_raw = load_json(RAW_DIR / "activities.json") or []
    body_battery_raw = load_json(RAW_DIR / "body_battery.json") or []
    weigh_ins_raw = load_json(RAW_DIR / "weigh_ins.json")

    daily = build_daily_series(stats_by_date, sleep_by_date, body_battery_raw)
    activities = build_activities(activities_raw)
    weight = build_weight(weigh_ins_raw)
    summary = build_summary(daily, activities, weight)

    dataset = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "daily": daily,
        "activities": activities,
        "weight": weight,
    }

    template_path = Path(__file__).parent / "dashboard_template.html"
    html = template_path.read_text()
    html = html.replace("__DATA_JSON__", json.dumps(dataset, ensure_ascii=False))

    OUT_PATH.write_text(html)
    print(f"Dashboard generata: {OUT_PATH}")
    print(f"  {summary['days']} giorni, {summary['totalActivities']} attività, "
          f"{len(weight)} pesate")


if __name__ == "__main__":
    main()
