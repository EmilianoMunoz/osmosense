from __future__ import annotations

import argparse
import os
from typing import Any

import requests
from dotenv import load_dotenv


DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_REGIONAL_EMAIL = "regional@osmosense.local"
DEFAULT_REGIONAL_PASSWORD = "regional123"


class SmokeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Smoke test no destructivo del flujo regional.")
    parser.add_argument("--api-url", default=None, help="URL base de FastAPI.")
    parser.add_argument(
        "--regional-email",
        default=os.getenv("OSMOSENSE_REGIONAL_EMAIL", DEFAULT_REGIONAL_EMAIL),
    )
    parser.add_argument(
        "--regional-password",
        default=os.getenv("OSMOSENSE_REGIONAL_PASSWORD", DEFAULT_REGIONAL_PASSWORD),
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


def assert_feature_collection(data: dict[str, Any], path: str) -> list[dict[str, Any]]:
    check(data.get("type") == "FeatureCollection", f"{path} no es FeatureCollection")
    features = data.get("features")
    check(isinstance(features, list), f"{path} no contiene lista features")
    check(len(features) > 0, f"{path} no contiene features")
    return features


def run() -> None:
    args = parse_args()
    api_url = base_url(args.api_url)
    print(f"API: {api_url}")

    health = request_json("GET", api_url, "/health", args.timeout)
    check(health.get("status") == "ok", "/health no devolvió status=ok")
    print("OK /health")

    auth = login(api_url, args.regional_email, args.regional_password, args.timeout)
    token = auth["access_token"]
    user = auth.get("user", {})
    check(user.get("rol") == "regional", "El login regional no devolvió rol=regional")
    check(user.get("view_mode") == "Regional", "El login regional no abre vista Regional")
    print("OK login regional")

    ranking = request_json("GET", api_url, "/regional/um/latest?limit=5", args.timeout, token)
    items = ranking.get("items")
    check(isinstance(items, list) and len(items) > 0, "/regional/um/latest no devolvió items")
    um_id = int(items[0].get("um_id"))
    check("ranking_um" in items[0], "/regional/um/latest no incluye ranking_um")
    print(f"OK /regional/um/latest count={ranking.get('count')} primera_um={um_id}")

    geojson = request_json("GET", api_url, "/regional/um/latest/geojson", args.timeout, token)
    features = assert_feature_collection(geojson, "/regional/um/latest/geojson")
    props = features[0].get("properties", {})
    check("prioridad_regional" in props, "/regional/um/latest/geojson no incluye prioridad")
    print(f"OK /regional/um/latest/geojson features={len(features)}")

    parcelas = request_json(
        "GET",
        api_url,
        f"/regional/um/{um_id}/parcelas/latest/geojson",
        args.timeout,
        token,
    )
    parcelas_features = assert_feature_collection(
        parcelas,
        "/regional/um/{um_id}/parcelas/latest/geojson",
    )
    check(parcelas.get("total_count", 0) > 0, "UM sin parcelas asociadas")
    print(f"OK /regional/um/{um_id}/parcelas/latest/geojson features={len(parcelas_features)}")

    request_json(
        "GET",
        api_url,
        "/admin/usuarios?limit=1",
        args.timeout,
        token,
        expected_status=403,
    )
    print("OK regional bloqueado en endpoint admin")

    request_json(
        "GET",
        api_url,
        "/clientes/1/rankings/latest/geojson",
        args.timeout,
        token,
        expected_status=403,
    )
    print("OK regional bloqueado en vista productor")

    print("SMOKE REGIONAL OK")


if __name__ == "__main__":
    try:
        run()
    except SmokeError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
