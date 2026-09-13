#!/bin/bash
# Scarica da Garmin, rigenera il sito cifrato e lo pubblica su GitHub Pages.
# Gira sul Mac perché Garmin blocca lo scambio dei token dai datacenter cloud.
#
# Uso:  ./publish.sh
# La passphrase viene letta dal Portachiavi, non è scritta da nessuna parte.

set -euo pipefail
cd "$(dirname "$0")"

LOG="logs/publish.log"
mkdir -p logs
exec > >(tee -a "$LOG") 2>&1
echo "=================================================="
echo "$(date '+%Y-%m-%d %H:%M:%S')  avvio sincronizzazione"

# La passphrase sta nel Portachiavi. Si imposta una volta sola con:
#   security add-generic-password -a "$USER" -s TRAINING_COACH_PASSPHRASE -w
if ! SITE_PASSPHRASE="$(security find-generic-password -a "$USER" \
        -s TRAINING_COACH_PASSPHRASE -w 2>/dev/null)"; then
  echo "ERRORE: passphrase non trovata nel Portachiavi."
  echo "Impostala una volta sola con:"
  echo "  security add-generic-password -a \"\$USER\" -s TRAINING_COACH_PASSPHRASE -w"
  exit 1
fi
export SITE_PASSPHRASE

source venv/bin/activate

echo "--- scarico da Garmin ---"
python -u scripts/fetch_data.py --days 120 --refresh-days 4

echo "--- rigenero il sito cifrato ---"
python -u scripts/build_site.py

echo "--- rigenero anche report e dashboard locali ---"
python -u scripts/build_report.py
python -u scripts/build_dashboard.py

echo "--- pubblico su GitHub ---"
if git diff --quiet docs/ 2>/dev/null && ! git status --porcelain docs/ | grep -q .; then
  echo "Nessuna modifica da pubblicare."
else
  git add docs/
  git commit -q -m "Report del $(date '+%Y-%m-%d %H:%M')"
  git push -q origin main
  echo "Pubblicato: https://andrea-b20.github.io/PERFORMANCE/"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S')  completato"
