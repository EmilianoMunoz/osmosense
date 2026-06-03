from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from dotenv import load_dotenv


HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260_000
TOKEN_ALGORITHM = "hmac_sha256"
TOKEN_TTL_SECONDS = 8 * 60 * 60
ROLE_ALIASES = {
    "cliente_particular": "productor",
    "cliente_regional": "regional",
}


def database_url() -> str | None:
    load_dotenv()
    return os.getenv("DATABASE_URL")


def auth_secret() -> str:
    load_dotenv()
    return os.getenv("AUTH_SECRET") or "estres-dev-auth-secret"


def normalize_role(rol: str) -> str:
    return ROLE_ALIASES.get(rol, rol)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def hash_password(password: str, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        HASH_ITERATIONS,
    )
    return "$".join(
        [
            HASH_ALGORITHM,
            str(HASH_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password or not password_hash:
        return False
    try:
        algorithm, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected = base64.b64decode(digest_text.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def _role_to_view(rol: str) -> str:
    rol = normalize_role(rol)
    if rol == "admin":
        return "Admin"
    if rol == "regional":
        return "Regional"
    return "Productor"


def _clean_user(row: dict[str, Any]) -> dict[str, Any]:
    rol = normalize_role(row["rol"])
    return {
        "usuario_id": int(row["usuario_id"]),
        "email": row["email"],
        "nombre": row.get("nombre"),
        "rol": rol,
        "cliente_id": int(row["cliente_id"]) if row.get("cliente_id") is not None else None,
        "view_mode": _role_to_view(rol),
    }


def create_access_token(user: dict[str, Any]) -> str:
    now = int(time.time())
    rol = normalize_role(user["rol"])
    payload = {
        "sub": str(user["usuario_id"]),
        "email": user["email"],
        "nombre": user.get("nombre"),
        "rol": rol,
        "cliente_id": user.get("cliente_id"),
        "view_mode": user.get("view_mode") or _role_to_view(rol),
        "iat": now,
        "exp": now + int(os.getenv("AUTH_TOKEN_TTL_SECONDS", TOKEN_TTL_SECONDS)),
    }
    payload_text = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64url_encode(payload_text)
    signature = hmac.new(
        auth_secret().encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{TOKEN_ALGORITHM}.{body}.{_b64url_encode(signature)}"


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        algorithm, body, signature_text = token.split(".", 2)
        if algorithm != TOKEN_ALGORITHM:
            raise ValueError
        expected = hmac.new(
            auth_secret().encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual = _b64url_decode(signature_text)
        if not hmac.compare_digest(actual, expected):
            raise ValueError
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Token inválido.") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expirado.")

    rol = normalize_role(payload["rol"])
    return {
        "usuario_id": int(payload["sub"]),
        "email": payload["email"],
        "nombre": payload.get("nombre"),
        "rol": rol,
        "cliente_id": (
            int(payload["cliente_id"]) if payload.get("cliente_id") is not None else None
        ),
        "view_mode": payload.get("view_mode") or _role_to_view(rol),
    }


def authenticate_user(email: str, password: str) -> dict[str, Any]:
    db_url = database_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL no configurado.")

    import psycopg
    from psycopg.rows import dict_row

    normalized_email = email.strip().lower()
    query = """
        SELECT usuario_id, email, nombre, rol, cliente_id, password_hash
        FROM usuarios
        WHERE lower(email) = %s
          AND activo = true
    """
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [normalized_email])
            row = cur.fetchone()
            if row is None or not verify_password(password, row["password_hash"]):
                raise ValueError("Credenciales inválidas.")
            cur.execute(
                "UPDATE usuarios SET last_login_at = now(), updated_at = now() WHERE usuario_id = %s",
                [row["usuario_id"]],
            )
        conn.commit()

    user = _clean_user(dict(row))
    return {
        "source": "postgis",
        "token_type": "bearer",
        "access_token": create_access_token(user),
        "user": user,
    }
