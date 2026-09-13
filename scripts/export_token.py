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
    use_file = "--file" in sys.argv

    if use_file:
        out = Path(__file__).parent.parent / "garmin_token.txt"
        out.write_text(token)
        out.chmod(0o600)
        print(f"Token scritto in: {out}")
        print(f"Lunghezza: {len(token)} caratteri\n")
        print("Aprilo, seleziona tutto (Cmd+A) e copia (Cmd+C).")
        print("CANCELLALO dopo averlo usato:")
        print(f'  rm "{out}"')
    else:
        subprocess.run(["pbcopy"], input=token.encode(), check=True)
        print(f"Token Garmin copiato negli appunti ({len(token)} caratteri).\n")
        print("Incollalo ORA con Cmd+V: se copi altro nel frattempo lo perdi")
        print("(in quel caso rilancia questo comando).\n")
        print("In alternativa, per averlo in un file che non si perde:")
        print("  python scripts/export_token.py --file")

    print("\nDove incollarlo:")
    print("  https://github.com/Andrea-B20/PERFORMANCE/settings/secrets/actions/new")
    print("  Name:   GARMIN_TOKEN")
    print("  Secret: il token")


if __name__ == "__main__":
    main()
