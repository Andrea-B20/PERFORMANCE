"""Autenticazione a Garmin Connect con cache del token locale.

Al primo avvio chiede email e password (inserite direttamente dall'utente
nel terminale) e salva il token di sessione in ~/.garminconnect. Alle
esecuzioni successive riusa il token senza richiedere le credenziali,
finché resta valido.
"""
import getpass
import os
import sys

from garth.exc import GarthException
from garminconnect import Garmin

TOKENSTORE = os.path.expanduser("~/.garminconnect")


def get_client() -> Garmin:
    # In CI il token arriva da una variabile d'ambiente (GitHub Secret).
    env_token = os.environ.get("GARMIN_TOKEN", "").strip()
    if env_token:
        print(f"Trovato GARMIN_TOKEN ({len(env_token)} caratteri).")
        if len(env_token) < 1000:
            raise SystemExit(
                f"ERRORE: il token sembra troncato ({len(env_token)} caratteri, "
                "ne servono circa 4300).\n"
                "Probabilmente è stato copiato solo in parte. Rigeneralo con:\n"
                "  python scripts/export_token.py --file\n"
                "poi apri il file, Cmd+A, Cmd+C e reincollalo nel secret GARMIN_TOKEN."
            )
        client = Garmin()
        try:
            client.garth.loads(env_token)
            client.display_name = client.garth.profile["displayName"]
            client.full_name = client.garth.profile["fullName"]
        except Exception as e:
            raise SystemExit(
                f"ERRORE: il token c'è ma Garmin lo rifiuta ({type(e).__name__}: {e}).\n"
                "Di solito significa che è scaduto. Rigeneralo sul Mac con:\n"
                "  python scripts/export_token.py --file\n"
                "e aggiorna il secret GARMIN_TOKEN."
            )
        print(f"Autenticato come {client.full_name} (token da GARMIN_TOKEN)")
        return client

    try:
        client = Garmin()
        client.login(TOKENSTORE)
        print(f"Autenticato come {client.full_name} (token riusato da {TOKENSTORE})")
        return client
    except (FileNotFoundError, GarthException, Exception):
        pass

    if not sys.stdin.isatty():
        raise SystemExit(
            "ERRORE: il secret GARMIN_TOKEN non è impostato (o è vuoto).\n\n"
            "Sul Mac esegui:\n"
            "  cd \"TRAINING COACH\" && source venv/bin/activate\n"
            "  python scripts/export_token.py --file\n\n"
            "Apri garmin_token.txt, copia TUTTO (Cmd+A, Cmd+C) e incollalo qui:\n"
            "  Settings → Secrets and variables → Actions → New repository secret\n"
            "  Name: GARMIN_TOKEN   (esattamente così, maiuscolo)\n\n"
            "Attenzione: dev'essere un *repository secret*, non un environment secret."
        )

    print("Nessun token valido trovato: effettua il login a Garmin Connect.")
    email = input("Garmin Connect email: ").strip()
    password = getpass.getpass("Garmin Connect password: ")

    client = Garmin(email=email, password=password)
    client.login()
    client.garth.dump(TOKENSTORE)
    print(f"Login riuscito. Token salvato in {TOKENSTORE} per i prossimi avvii.")
    return client
