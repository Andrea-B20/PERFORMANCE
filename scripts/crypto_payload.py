"""Cifratura del payload compatibile con la WebCrypto API del browser.

Schema: PBKDF2-HMAC-SHA256 (600k iterazioni) -> chiave AES-256-GCM.
Il browser decifra con crypto.subtle usando gli stessi parametri.
La passphrase non viene mai salvata: senza di essa il payload è inutilizzabile.
"""
import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600_000


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def encrypt(payload: dict, passphrase: str) -> dict:
    if not passphrase:
        raise ValueError("Passphrase mancante: impossibile cifrare il payload")

    salt = os.urandom(16)
    iv = os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=ITERATIONS).derive(passphrase.encode("utf-8"))
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(iv, plaintext, None)

    return {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iterations": ITERATIONS,
        "cipher": "AES-256-GCM",
        "salt": _b64(salt),
        "iv": _b64(iv),
        "data": _b64(ciphertext),
    }
