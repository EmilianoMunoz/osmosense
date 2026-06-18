from __future__ import annotations

import argparse
import os
import sys
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
    parser = argparse.ArgumentParser(
        description=(
            "Smoke test mutante del CRUD productor-parcela. Asigna una parcela "
            "libre a un productor, valida que aparezca en su vista y luego la "
            "desasigna para restaurar el estado inicial."
        )
    )
    parser.add_argument("--api-url", default=None, help="URL base de FastAPI.")
    parser.add_argument("--admin-email", default=DEFAULT_ADMIN_EMAIL)
    parser.add_argument("--admin-password", default=DEFAULT_ADMIN_PASSWORD)
    parser.add_argument("--productor-email", default=DEFAULT_PRODUCTOR_EMAIL)
    parser.add_argument("--productor-password", default=DEFAULT_PRODUCTOR_PASSWORD)
    parser.add_argument("--parcela-id", type=int, default=None, help="Parcela libre específica.")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--confirm-mutating",
        action="store_true",
        help="Requerido para ejecutar el test porque modifica temporalmente PostGIS.",
    )
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
    if not response.text:
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


def item_ids(items: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for item in items:
        try:
            ids.add(int(item["parcela_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return ids


def feature_ids(geojson: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        try:
            ids.add(int(props["parcela_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return ids


def productor_parcelas(
    api_url: str,
    productor_token: str,
    timeout: float,
) -> set[int]:
    data = request_json("GET", api_url, "/me/parcelas", timeout, productor_token)
    items = data.get("items")
    check(isinstance(items, list), "/me/parcelas no devolvió items")
    return item_ids(items)


def productor_geojson_ids(
    api_url: str,
    productor_token: str,
    timeout: float,
) -> set[int]:
    data = request_json("GET", api_url, "/me/rankings/latest/geojson", timeout, productor_token)
    check(data.get("type") == "FeatureCollection", "/me/rankings/latest/geojson no es FeatureCollection")
    return feature_ids(data)


def choose_free_parcela(
    api_url: str,
    admin_token: str,
    timeout: float,
    parcela_id: int | None = None,
) -> int:
    if parcela_id is not None:
        data = request_json(
            "GET",
            api_url,
            "/admin/parcelas?limit=5000&activo=true&sin_asignar=true",
            timeout,
            admin_token,
        )
        free_ids = item_ids(data.get("items", []))
        check(
            parcela_id in free_ids,
            f"La parcela {parcela_id} no está libre para asignar.",
        )
        return parcela_id

    data = request_json(
        "GET",
        api_url,
        "/admin/parcelas?limit=20&activo=true&sin_asignar=true",
        timeout,
        admin_token,
    )
    items = data.get("items")
    check(isinstance(items, list), "/admin/parcelas no devolvió items")
    check(len(items) > 0, "No hay parcelas libres para probar asignación.")
    return int(items[0]["parcela_id"])


def cleanup_relation(
    api_url: str,
    admin_token: str,
    timeout: float,
    cliente_id: int,
    parcela_id: int,
) -> None:
    response = requests.delete(
        f"{api_url}/admin/clientes/{cliente_id}/parcelas/{parcela_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=timeout,
    )
    if response.status_code in {200, 404}:
        return
    raise SmokeError(
        f"Cleanup DELETE devolvió HTTP {response.status_code}: {response.text[:300]}"
    )


def run() -> int:
    args = parse_args()
    if not args.confirm_mutating:
        raise SmokeError("Este smoke modifica relaciones. Ejecutar con --confirm-mutating.")

    api_url = base_url(args.api_url)
    print(f"API: {api_url}")

    health = request_json("GET", api_url, "/health", args.timeout)
    check(health.get("status") == "ok", "/health no devolvió status=ok")
    print("OK /health")

    admin_auth = login(api_url, args.admin_email, args.admin_password, args.timeout)
    admin_token = admin_auth["access_token"]
    check(admin_auth.get("user", {}).get("rol") == "admin", "El login admin no devolvió rol=admin")
    print("OK login admin")

    productor_auth = login(api_url, args.productor_email, args.productor_password, args.timeout)
    productor_token = productor_auth["access_token"]
    productor_user = productor_auth.get("user", {})
    check(productor_user.get("rol") == "productor", "El login productor no devolvió rol=productor")
    cliente_id = productor_user.get("cliente_id")
    check(cliente_id is not None, "El productor no tiene cliente_id/cartera asignada")
    cliente_id = int(cliente_id)
    print(f"OK login productor cliente_id={cliente_id}")

    parcela_id = choose_free_parcela(api_url, admin_token, args.timeout, args.parcela_id)
    print(f"Parcela libre seleccionada: {parcela_id}")

    before_ids = productor_parcelas(api_url, productor_token, args.timeout)
    check(parcela_id not in before_ids, "La parcela elegida ya estaba en la vista del productor")

    assigned = False
    original_error: Exception | None = None
    try:
        request_json(
            "POST",
            api_url,
            f"/admin/clientes/{cliente_id}/parcelas",
            args.timeout,
            admin_token,
            expected_status=201,
            json={"parcela_id": parcela_id, "etiqueta": "smoke-crud"},
        )
        assigned = True
        print("OK asignación admin")

        after_assign_ids = productor_parcelas(api_url, productor_token, args.timeout)
        check(parcela_id in after_assign_ids, "La parcela asignada no aparece en /me/parcelas")

        after_assign_geo_ids = productor_geojson_ids(api_url, productor_token, args.timeout)
        check(
            parcela_id in after_assign_geo_ids,
            "La parcela asignada no aparece en /me/rankings/latest/geojson",
        )
        print("OK productor ve la parcela asignada")
    except Exception as exc:
        original_error = exc
    finally:
        if assigned:
            cleanup_relation(api_url, admin_token, args.timeout, cliente_id, parcela_id)
            print("OK cleanup desasignación admin")

    if original_error is not None:
        raise original_error

    after_cleanup_ids = productor_parcelas(api_url, productor_token, args.timeout)
    check(parcela_id not in after_cleanup_ids, "La parcela sigue apareciendo en /me/parcelas")

    after_cleanup_geo_ids = productor_geojson_ids(api_url, productor_token, args.timeout)
    check(
        parcela_id not in after_cleanup_geo_ids,
        "La parcela sigue apareciendo en /me/rankings/latest/geojson",
    )
    print("OK productor dejó de ver la parcela desasignada")
    print("SMOKE CRUD PRODUCTOR OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SmokeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
