"""Esporta il token Garmin negli appunti, per incollarlo nei GitHub Secrets.

Il token NON viene stampato a schermo: finisce direttamente negli appunti,
così non resta nella cronologia del terminale.

Uso:
    python scripts/export_token.py
"""
import subprocess
import sys
from pathlib import Path

TOKENSTORE = Path.home() / ".garminconnect"


def main():
    if not TOKENSTORE.exists():
        sys.exit(f"Nessun token trovato in {TOKENSTORE}.\n"
                 "Esegui prima: python scripts/fetch_data.py --days 7")

    import garth
    client = garth.Client()
    try:
        client.load(str(TOKENSTORE))
    except Exception as e:
        sys.exit(f"Token non leggibile ({e}). Rifai il login con fetch_data.py.")

    token = client.dumps()

    try:
        subprocess.run(["pbcopy"], input=token.encode(), check=True)
        where = "negli appunti"
    except Exception:
        out = Path(__file__).parent.parent / "garmin_token.txt"
        out.write_text(token)
        out.chmod(0o600)
        where = f"nel file {out} (cancellalo dopo averlo usato)"

    print(f"Token Garmin copiato {where}.")
    print(f"Lunghezza: {len(token)} caratteri\n")
    print("Ora su GitHub: Settings → Secrets and variables → Actions → New repository secret")
    print("  Nome:   GARMIN_TOKEN")
    print("  Valore: incolla (Cmd+V)")


if __name__ == "__main__":
    main()
