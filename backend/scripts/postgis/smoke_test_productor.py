from __future__ import annotations

import argparse
import os
from typing import Any

import requests
from dotenv import load_dotenv


DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_ADMIN_EMAIL = "admin@osmosense.local"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_PRODUCTOR_EMAIL = "productor.vid@osmosense.local"
DEFAULT_PRODUCTOR_PASSWORD = "cliente123"


class SmokeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Smoke test no destructivo del flujo productor-parcela."
    )
    parser.add_argument("--api-url", default=None, help="URL base de FastAPI.")
    parser.add_argument(
        "--admin-email",
        default=os.getenv("OSMOSENSE_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL),
    )
    parser.add_argument(
        "--admin-password",
        default=os.getenv("OSMOSENSE_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD),
    )
    parser.add_argument(
        "--productor-email",
        default=os.getenv("OSMOSENSE_PRODUCTOR_EMAIL", DEFAULT_PRODUCTOR_EMAIL),
    )
    parser.add_argument(
        "--productor-password",
        default=os.getenv("OSMOSENSE_PRODUCTOR_PASSWORD", DEFAULT_PRODUCTOR_PASSWORD),
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def base_url(cli_value: str | None) -> str:
    load_dotenv()
    return (cli_value or os.getenv("API_BASE_URL") or DEFAULT_API_URL).rstrip("/")


def request_json(
    method: str,
    api_url: str,
    path: str,
    timeout: float,
    token: str | None = None,
    expected_status: int = 200,
    **kwargs: Any,
) -> dict[str, Any]:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.request(
        method,
        f"{api_url}{path}",
        headers=headers or None,
        timeout=timeout,
        **kwargs,
    )
    check(
        response.status_code == expected_status,
        f"{method} {path} devolvió HTTP {response.status_code}, esperado "
        f"{expected_status}: {response.text[:300]}",
    )
    if expected_status == 204 or not response.text:
        return {}
    data = response.json()
    check(isinstance(data, dict), f"{method} {path} no devolvió un objeto JSON")
    return data


def login(api_url: str, email: str, password: str, timeout: float) -> dict[str, Any]:
    data = request_json(
        "POST",
        api_url,
        "/auth/login",
        timeout,
        json={"email": email, "password": password},
    )
    token = data.get("access_token")
    check(isinstance(token, str) and token, f"Login sin access_token para {email}")
    return data


def run() -> None:
    args = parse_args()
    api_url = base_url(args.api_url)
    print(f"API: {api_url}")

    health = request_json("GET", api_url, "/health", args.timeout)
    check(health.get("status") == "ok", "/health no devolvió status=ok")
    print("OK /health")

    admin_auth = login(api_url, args.admin_email, args.admin_password, args.timeout)
    admin_token = admin_auth["access_token"]
    check(admin_auth.get("user", {}).get("rol") == "admin", "El login admin no devolvió rol=admin")
    print("OK login admin")

    usuarios = request_json(
        "GET",
        api_url,
        "/admin/usuarios?limit=5000&activo=true",
        args.timeout,
        token=admin_token,
    )
    productores = [
        item for item in usuarios.get("items", [])
        if item.get("rol") == "productor"
    ]
    check(len(productores) > 0, "No hay usuarios productores activos")
    print(f"OK productores activos={len(productores)}")

    libres = request_json(
        "GET",
        api_url,
        "/admin/parcelas?limit=5&activo=true&sin_asignar=true",
        args.timeout,
        token=admin_token,
    )
    check(libres.get("source") == "postgis", "/admin/parcelas no usa PostGIS")
    check(isinstance(libres.get("items"), list), "/admin/parcelas no devolvió items")
    print(f"OK parcelas analizables sin productor consultadas={libres.get('count')}")

    productor_auth = login(api_url, args.productor_email, args.productor_password, args.timeout)
    productor_user = productor_auth.get("user", {})
    productor_token = productor_auth["access_token"]
    check(productor_user.get("rol") == "productor", "El login productor no devolvió rol=productor")
    productor_cliente_id = productor_user.get("cliente_id")
    check(productor_cliente_id is not None, "El productor no tiene parcelas asignadas")
    print(f"OK login productor cliente_id={productor_cliente_id}")

    admin_parcelas_productor = request_json(
        "GET",
        api_url,
        f"/admin/clientes/{int(productor_cliente_id)}/parcelas",
        args.timeout,
        token=admin_token,
    )
    check(
        admin_parcelas_productor.get("count", 0) > 0,
        "El productor no tiene parcelas asignadas según vista admin",
    )
    print(f"OK parcelas asignadas admin={admin_parcelas_productor.get('count')}")

    productor_geojson = request_json(
        "GET",
        api_url,
        f"/clientes/{int(productor_cliente_id)}/rankings/latest/geojson",
        args.timeout,
        token=productor_token,
    )
    features = productor_geojson.get("features")
    check(isinstance(features, list), "La vista productor no devolvió features")
    check(len(features) > 0, "La vista productor no tiene parcelas")
    print(f"OK vista productor features={len(features)}")

    request_json(
        "GET",
        api_url,
        "/admin/usuarios?limit=1",
        args.timeout,
        token=productor_token,
        expected_status=403,
    )
    print("OK productor bloqueado en endpoint admin")

    print("SMOKE PRODUCTOR OK")


if __name__ == "__main__":
    try:
        run()
    except SmokeError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
