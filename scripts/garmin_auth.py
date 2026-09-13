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


def annotate(exc: Exception, detail: str) -> None:
    """Su GitHub Actions mostra l'errore nel riquadro Annotations della pagina
    di riepilogo, così è leggibile senza aprire i log."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    status = getattr(getattr(exc, "response", None), "status_code", None)
    title = f"Garmin ha rifiutato la connessione (HTTP {status})" if status \
        else f"Autenticazione Garmin fallita ({type(exc).__name__})"
    body = detail.replace("\r", "").replace("\n", "%0A")
    print(f"::error title={title}::{body}", flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(f"## Errore di autenticazione Garmin\n\n```\n{detail}\n```\n")


def diagnose_failure(exc: Exception) -> str:
    """Distingue un token scaduto da un blocco di Garmin sull'IP del runner.

    Garmin filtra spesso il traffico proveniente dai datacenter cloud: in quel
    caso lo stesso token che funziona da casa viene rifiutato in CI.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    lines = [
        "=" * 64,
        f"ERRORE DI AUTENTICAZIONE GARMIN: {type(exc).__name__}",
        f"Messaggio: {exc}",
        f"HTTP status: {status if status else 'nessuno (errore non HTTP)'}",
        "=" * 64,
    ]

    try:
        import urllib.request
        req = urllib.request.Request(
            "https://connect.garmin.com/signin",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            probe = f"raggiungibile (HTTP {r.status})"
    except Exception as pe:
        probe = f"NON raggiungibile ({type(pe).__name__}: {pe})"
    lines.append(f"Raggiungibilità di connect.garmin.com da qui: {probe}")

    if status in (401, 403):
        lines += [
            "",
            "Status 401/403 con un token che funziona dal tuo computer significa",
            "quasi sempre che Garmin sta bloccando l'indirizzo IP del runner:",
            "i server di GitHub Actions stanno in datacenter, e Garmin filtra",
            "quel traffico. Non è un problema del token né della configurazione.",
            "",
            "In questo caso la sincronizzazione va spostata sul tuo Mac.",
        ]
    else:
        lines += [
            "",
            "Se il token è scaduto, rigeneralo sul Mac con:",
            "  python scripts/export_token.py --file",
            "e aggiorna il secret GARMIN_TOKEN.",
        ]
    return "\n".join(lines)


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
            msg = diagnose_failure(e)
            annotate(e, msg)
            raise SystemExit(msg)
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
