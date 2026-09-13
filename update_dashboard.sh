#!/bin/bash
# Aggiorna i dati Garmin e rigenera dashboard.html.
# Uso: ./update_dashboard.sh [giorni]   (default 90)
set -e
cd "$(dirname "$0")"
source venv/bin/activate
DAYS="${1:-90}"
python scripts/fetch_data.py --days "$DAYS"
python scripts/build_dashboard.py
python scripts/build_report.py
echo
echo "Pronti: dashboard.html (dati) e report.html (referto tecnico)."
