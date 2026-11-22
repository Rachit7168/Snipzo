"""Password hashing, bearer tokens, and signed download links (stdlib only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def hash_password(password: str) -> str:
    """Return a salted scrypt hash string."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(
        password.encode(),
        salt=_unb64(salt_b64),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return hmac.compare_digest(digest, _unb64(digest_b64))


def sign(payload: dict[str, object], secret: str, ttl_seconds: int) -> str:
    """Return `body.signature` where body is base64 JSON with an `exp` claim."""
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl_seconds
    raw = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    return f"{raw}.{_mac(raw, secret)}"


def unsign(token: str, secret: str) -> dict[str, object] | None:
    """Return the payload when the signature is valid and not expired."""
    try:
        raw, mac = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(mac, _mac(raw, secret)):
        return None
    try:
        body = json.loads(_unb64(raw))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    exp = body.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    return body


def _mac(raw: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest())


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
