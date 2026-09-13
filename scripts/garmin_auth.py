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
        client = Garmin()
        client.garth.loads(env_token)
        client.display_name = client.garth.profile["displayName"]
        client.full_name = client.garth.profile["fullName"]
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
            "Nessun token valido e nessun terminale interattivo.\n"
            "In CI imposta il secret GARMIN_TOKEN (vedi scripts/export_token.py)."
        )

    print("Nessun token valido trovato: effettua il login a Garmin Connect.")
    email = input("Garmin Connect email: ").strip()
    password = getpass.getpass("Garmin Connect password: ")

    client = Garmin(email=email, password=password)
    client.login()
    client.garth.dump(TOKENSTORE)
    print(f"Login riuscito. Token salvato in {TOKENSTORE} per i prossimi avvii.")
    return client
