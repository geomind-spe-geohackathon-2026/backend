import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.core.settings import settings

PURPOSE = b"geomind connector secrets"


def cipher() -> Fernet:
    """Return the cipher of stored secrets, keyed from the app's signing secret."""
    digest = hashlib.sha256(PURPOSE + settings.JWT_SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(secret: str) -> str:
    """Encrypt a secret for storage."""
    return cipher().encrypt(secret.encode()).decode()


def unseal(sealed: str) -> str | None:
    """Return a stored secret, or ``None`` when the signing secret changed since."""
    try:
        return cipher().decrypt(sealed.encode()).decode()
    except InvalidToken:
        return None
