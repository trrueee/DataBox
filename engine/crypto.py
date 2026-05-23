import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_FILE = Path(__file__).resolve().parent / ".secret_key"


def get_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = AESGCM.generate_key(bit_length=256)  # type: ignore[call-arg]
    KEY_FILE.write_bytes(key)
    return key


def encrypt_password(password: str) -> tuple[str, str]:
    """Encrypts a database password using AES-256-GCM.

    Returns (ciphertext_b64, nonce_b64).
    """
    if not password:
        return "", ""
    key = get_or_create_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    data = password.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data, None)

    ciphertext_b64 = base64.b64encode(ciphertext).decode("utf-8")
    nonce_b64 = base64.b64encode(nonce).decode("utf-8")
    return ciphertext_b64, nonce_b64


def decrypt_password(ciphertext_b64: str, nonce_b64: str) -> str:
    """Decrypts an AES-256-GCM encrypted database password.

    Returns the plain password.
    """
    if not ciphertext_b64 or not nonce_b64:
        return ""
    key = get_or_create_key()
    aesgcm = AESGCM(key)
    try:
        ciphertext = base64.b64decode(ciphertext_b64.encode("utf-8"))
        nonce = base64.b64decode(nonce_b64.encode("utf-8"))
        data = aesgcm.decrypt(nonce, ciphertext, None)
        return data.decode("utf-8")
    except Exception:
        raise ValueError("Failed to decrypt database credentials") from None
