from __future__ import annotations

import re
from typing import Any

from backend.app.services.auth import database_url, hash_password, normalize_role


VALID_ROLES = {"admin", "regional", "productor"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DNI_RE = re.compile(r"^\d{7,9}$")


def _db_url() -> str:
    db_url = database_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL no configurado.")
    return db_url


def _validate_role_payload(data: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data.copy()
    if "email" in payload and payload["email"] is not None:
        email = str(payload["email"]).strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("El email no tiene un formato válido.")
        payload["email"] = email

    if "rol" in payload and payload["rol"] is not None:
        payload["rol"] = normalize_role(str(payload["rol"]))
        if payload["rol"] not in VALID_ROLES:
            raise ValueError("Rol inválido.")

    if "dni" in payload and payload["dni"] is not None:
        dni = str(payload["dni"]).strip().replace(".", "").replace(" ", "").replace("-", "")
        payload["dni"] = dni or None
        if payload["dni"] and not DNI_RE.match(payload["dni"]):
            raise ValueError("El DNI debe contener entre 7 y 9 dígitos.")

    rol = payload.get("rol")
    if rol is None and current is not None:
        rol = normalize_role(str(current["rol"]))

    cliente_id = payload.get("cliente_id")
    if cliente_id is None and current is not None and "cliente_id" not in payload:
        cliente_id = current.get("cliente_id")

    if rol in {"admin", "regional"}:
        payload["cliente_id"] = None

    target_active = bool(payload.get("activo", current.get("activo", True) if current is not None else True))

    if rol == "productor" and target_active:
        apellido = payload.get("apellido")
        if apellido is None and current is not None:
            apellido = current.get("apellido")
        dni = payload.get("dni")
        if dni is None and current is not None:
            dni = current.get("dni")
        if not str(apellido or "").strip():
            raise ValueError("El apellido es obligatorio para usuarios productores.")
        if not str(dni or "").strip():
            raise ValueError("El DNI es obligatorio para usuarios productores.")
        if not DNI_RE.match(str(dni).strip()):
            raise ValueError("El DNI debe contener entre 7 y 9 dígitos.")

    return payload


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["rol"] = normalize_role(str(item["rol"]))
    item.pop("password_hash", None)
    if item.get("cliente_id") is not None:
        item["cliente_id"] = int(item["cliente_id"])
    if item.get("usuario_id") is not None:
        item["usuario_id"] = int(item["usuario_id"])
    return item


def admin_usuarios(limit: int | None = None, activo: bool | None = None) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    filters = []
    params: list[Any] = []
    if activo is not None:
        filters.append("u.activo = %s")
        params.append(activo)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        params.append(int(limit))

    query = f"""
        SELECT
            u.usuario_id,
            u.email,
            u.nombre,
            u.apellido,
            u.dni,
            u.rol,
            u.cliente_id,
            c.nombre AS productor_nombre,
            c.tipo AS productor_tipo,
            u.activo,
            u.last_login_at,
            u.created_at,
            u.updated_at
        FROM usuarios u
        LEFT JOIN clientes c
            ON c.cliente_id = u.cliente_id
        {where}
        ORDER BY u.activo DESC, u.rol, u.email
        {limit_sql}
    """
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = [_public_user(dict(row)) for row in cur.fetchall()]

    return {"source": "postgis", "count": len(rows), "items": rows}


def admin_create_usuario(data: dict[str, Any]) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    password = data.get("password")
    if not password:
        raise ValueError("La contraseña es obligatoria.")

    payload = _validate_role_payload(data)
    query = """
        INSERT INTO usuarios (
            email,
            nombre,
            apellido,
            dni,
            rol,
            cliente_id,
            password_hash,
            activo,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
        RETURNING
            usuario_id,
            email,
            nombre,
            apellido,
            dni,
            rol,
            cliente_id,
            activo,
            last_login_at,
            created_at,
            updated_at
    """
    params = [
        str(payload["email"]).strip().lower(),
        payload.get("nombre"),
        payload.get("apellido"),
        payload.get("dni"),
        payload["rol"],
        payload.get("cliente_id"),
        hash_password(str(password)),
        bool(payload.get("activo", True)),
    ]
    try:
        with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = dict(cur.fetchone())
            conn.commit()
    except psycopg.errors.UniqueViolation as exc:
        raise ValueError("Ya existe un usuario con ese email.") from exc
    except psycopg.errors.ForeignKeyViolation as exc:
        raise ValueError("El productor/campo asociado no existe.") from exc

    return {"source": "postgis", "item": _public_user(row)}


def admin_update_usuario(usuario_id: int, data: dict[str, Any]) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    if not data:
        raise ValueError("No hay campos para actualizar.")

    try:
        with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT usuario_id, rol, cliente_id, apellido, dni, activo
                    FROM usuarios
                    WHERE usuario_id = %s
                    """,
                    [int(usuario_id)],
                )
                current = cur.fetchone()
                if current is None:
                    raise ValueError("Usuario no encontrado.")

                payload = _validate_role_payload(data, dict(current))
                current_dict = dict(current)
                current_is_active_admin = (
                    normalize_role(str(current_dict["rol"])) == "admin"
                    and bool(current_dict.get("activo", True))
                )
                target_role = normalize_role(str(payload.get("rol", current_dict["rol"])))
                target_active = bool(payload.get("activo", current_dict.get("activo", True)))
                if current_is_active_admin and (target_role != "admin" or not target_active):
                    cur.execute(
                        """
                        SELECT count(*)
                        FROM usuarios
                        WHERE rol = 'admin'
                          AND activo = true
                          AND usuario_id <> %s
                        """,
                        [int(usuario_id)],
                    )
                    other_admins = int(cur.fetchone()["count"])
                    if other_admins == 0:
                        raise ValueError("No se puede desactivar o cambiar el último admin activo.")

                allowed = ["email", "nombre", "apellido", "dni", "rol", "cliente_id", "activo"]
                assignments = []
                params: list[Any] = []
                for field in allowed:
                    if field not in payload:
                        continue
                    value = payload[field]
                    if field == "email" and value is not None:
                        value = str(value).strip().lower()
                    assignments.append(f"{field} = %s")
                    params.append(value)

                if payload.get("password"):
                    assignments.append("password_hash = %s")
                    params.append(hash_password(str(payload["password"])))

                if not assignments:
                    raise ValueError("No hay campos válidos para actualizar.")

                assignments.append("updated_at = now()")
                params.append(int(usuario_id))
                cur.execute(
                    f"""
                    UPDATE usuarios
                    SET {', '.join(assignments)}
                    WHERE usuario_id = %s
                    RETURNING
                        usuario_id,
                        email,
                        nombre,
                        apellido,
                        dni,
                        rol,
                        cliente_id,
                        activo,
                        last_login_at,
                        created_at,
                        updated_at
                    """,
                    params,
                )
                row = dict(cur.fetchone())
            conn.commit()
    except psycopg.errors.UniqueViolation as exc:
        raise ValueError("Ya existe un usuario con ese email.") from exc
    except psycopg.errors.ForeignKeyViolation as exc:
        raise ValueError("El productor/campo asociado no existe.") from exc

    return {"source": "postgis", "item": _public_user(row)}


def admin_deactivate_usuario(usuario_id: int) -> dict[str, Any]:
    result = admin_update_usuario(int(usuario_id), {"activo": False})
    return {
        "source": result["source"],
        "deleted": True,
        "usuario_id": int(usuario_id),
        "item": result["item"],
    }
