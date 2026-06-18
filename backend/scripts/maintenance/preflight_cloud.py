from __future__ import annotations

import argparse
import os
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.auth import validate_auth_secret, verify_password


FALSE_VALUES = {"0", "false", "no", "off"}
PRODUCTION_VALUES = {"prod", "production"}
DEFAULT_DEMO_CREDENTIALS = {
    "admin@osmosense.local": "admin123",
    "productor.vid@osmosense.local": "cliente123",
    "productor.olivo@osmosense.local": "cliente123",
    "regional@osmosense.local": "regional123",
}
CONFIG: dict[str, str] = {}


@dataclass
class Finding:
    level: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida configuración mínima antes de desplegar OSMOSENSE en cloud."
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Conecta a DATABASE_URL y valida PostGIS/usuarios demo.",
    )
    return parser.parse_args()


def env(name: str, default: str = "") -> str:
    value = CONFIG.get(name)
    if value is None:
        value = os.getenv(name, default)
    return str(value or "").strip()


def is_false(value: str) -> bool:
    return value.strip().lower() in FALSE_VALUES


def add(
    findings: list[Finding],
    level: str,
    message: str,
) -> None:
    findings.append(Finding(level=level, message=message))


def mask_database_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except Exception:
        return "<url inválida>"
    if not parsed.scheme:
        return "<url sin scheme>"
    host = parsed.hostname or "-"
    port = f":{parsed.port}" if parsed.port else ""
    user = parsed.username or "-"
    return f"{parsed.scheme}://{user}:***@{host}{port}{parsed.path}"


def check_env_file(path: Path, findings: list[Finding]) -> None:
    if not path.exists():
        add(findings, "FAIL", f"No existe {path}.")
        return

    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        add(
            findings,
            "FAIL",
            f"{path} tiene permisos {oct(mode)}; usar chmod 600 {path}.",
        )
    else:
        add(findings, "OK", f"{path} tiene permisos restringidos.")


def check_required_env(findings: list[Finding]) -> None:
    app_env = env("APP_ENV") or env("OSMOSENSE_ENV") or env("ENVIRONMENT")
    if app_env.lower() not in PRODUCTION_VALUES:
        add(findings, "FAIL", "APP_ENV debe ser production para la demo cloud.")
    else:
        add(findings, "OK", "APP_ENV=production.")

    if not is_false(env("ENABLE_LOCAL_FALLBACK", "true")):
        add(findings, "FAIL", "ENABLE_LOCAL_FALLBACK debe ser false en cloud.")
    else:
        add(findings, "OK", "Fallback local deshabilitado.")

    if not is_false(env("ENABLE_QUICK_LOGIN", "true")):
        add(findings, "FAIL", "ENABLE_QUICK_LOGIN debe ser false en cloud.")
    else:
        add(findings, "OK", "Login rápido deshabilitado.")

    database_url = env("DATABASE_URL")
    if not database_url:
        add(findings, "FAIL", "DATABASE_URL es obligatorio.")
    else:
        add(findings, "OK", "DATABASE_URL configurado.")
        if "estres_dev" in database_url:
            add(findings, "WARN", "DATABASE_URL usa credencial dev estres_dev.")

    api_base_url = env("API_BASE_URL")
    if not api_base_url:
        add(findings, "FAIL", "API_BASE_URL es obligatorio para Streamlit.")
    else:
        add(findings, "OK", "API_BASE_URL configurado.")
        if "127.0.0.1" in api_base_url or "localhost" in api_base_url:
            add(findings, "WARN", "API_BASE_URL apunta a localhost; validar si aplica en la VM.")

    auth_secret = env("AUTH_SECRET")
    if not auth_secret:
        add(findings, "FAIL", "AUTH_SECRET es obligatorio.")
    else:
        try:
            validate_auth_secret(auth_secret, production=True)
        except RuntimeError as exc:
            add(findings, "FAIL", str(exc))
        else:
            add(findings, "OK", "AUTH_SECRET cumple mínimo de producción.")

    if not env("GEE_PROJECT_ID"):
        add(findings, "FAIL", "GEE_PROJECT_ID es obligatorio para pipeline Sentinel/GEE.")
    else:
        add(findings, "OK", "GEE_PROJECT_ID configurado.")


def check_deployment_files(findings: list[Finding]) -> None:
    required = [
        "deployment/systemd/osmosense-api.service",
        "deployment/systemd/osmosense-dashboard.service",
        "deployment/systemd/osmosense-pipeline.service",
        "deployment/systemd/osmosense-pipeline.timer",
        "deployment/systemd/osmosense-postgis-backup.service",
        "deployment/systemd/osmosense-postgis-backup.timer",
    ]
    missing = [path for path in required if not Path(path).exists()]
    if missing:
        add(findings, "FAIL", "Faltan plantillas systemd: " + ", ".join(missing))
    else:
        add(findings, "OK", "Plantillas systemd OSMOSENSE presentes.")


def check_database(findings: list[Finding]) -> None:
    database_url = env("DATABASE_URL")
    if not database_url:
        return

    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        add(findings, "FAIL", f"No se pudo importar psycopg: {exc}")
        return

    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            with psycopg.connect(database_url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS ok")
                    cur.fetchone()
                    add(findings, "OK", "Conexión PostGIS disponible.")

                    cur.execute("SELECT postgis_version() AS version")
                    version = cur.fetchone()["version"]
                    add(findings, "OK", f"Extension PostGIS activa: {version}.")

                    cur.execute("SELECT count(*) AS count FROM usuarios WHERE activo = true")
                    users_count = int(cur.fetchone()["count"])
                    if users_count == 0:
                        add(findings, "FAIL", "No hay usuarios activos.")
                    else:
                        add(findings, "OK", f"Usuarios activos: {users_count}.")

                    cur.execute(
                        """
                        SELECT email, password_hash
                        FROM usuarios
                        WHERE lower(email) = ANY(%s)
                        """,
                        [[email.lower() for email in DEFAULT_DEMO_CREDENTIALS]],
                    )
                    weak_users = []
                    for row in cur.fetchall():
                        expected_password = DEFAULT_DEMO_CREDENTIALS.get(row["email"].lower())
                        if expected_password and verify_password(
                            expected_password,
                            row["password_hash"],
                        ):
                            weak_users.append(row["email"])
                    if weak_users:
                        add(
                            findings,
                            "FAIL",
                            "Credenciales demo activas: " + ", ".join(sorted(weak_users)),
                        )
                    else:
                        add(findings, "OK", "No se detectaron contraseñas demo conocidas.")

                    cur.execute("SELECT count(*) AS count FROM parcelas WHERE activo = true")
                    parcelas_count = int(cur.fetchone()["count"])
                    if parcelas_count == 0:
                        add(findings, "FAIL", "No hay parcelas activas.")
                    else:
                        add(findings, "OK", f"Parcelas activas: {parcelas_count}.")
                    return
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(0.5)

    if last_exc is not None:
        add(
            findings,
            "FAIL",
            "Chequeo DB falló "
            f"({type(last_exc).__name__}) en {mask_database_url(database_url)}: {last_exc}",
        )


def print_report(findings: list[Finding]) -> None:
    print("=== Preflight cloud OSMOSENSE ===")
    for finding in findings:
        print(f"[{finding.level}] {finding.message}")
    fails = sum(1 for item in findings if item.level == "FAIL")
    warns = sum(1 for item in findings if item.level == "WARN")
    print(f"Resultado: {fails} fallas, {warns} advertencias.")


def main() -> int:
    args = parse_args()
    global CONFIG
    CONFIG = {
        key: value
        for key, value in dotenv_values(args.env_file).items()
        if value is not None
    }

    findings: list[Finding] = []
    check_env_file(Path(args.env_file), findings)
    check_required_env(findings)
    check_deployment_files(findings)
    if args.check_db:
        check_database(findings)

    print_report(findings)
    return 1 if any(item.level == "FAIL" for item in findings) else 0


if __name__ == "__main__":
    from backend.scripts.maintenance.preflight_cloud import main as package_main

    raise SystemExit(package_main())
