from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv


DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_DATABASE_URL = "postgresql://estres:estres_dev@127.0.0.1:5433/estres"


class SmokeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test operativo para API, PostGIS y fallback local."
    )
    parser.add_argument("--api-url", default=None, help="URL base de FastAPI.")
    parser.add_argument(
        "--require-source",
        choices=["any", "csv", "postgis"],
        default="any",
        help="Fuente esperada en endpoints de la API.",
    )
    parser.add_argument("--skip-api", action="store_true", help="No consulta FastAPI.")
    parser.add_argument(
        "--check-postgis",
        action="store_true",
        help="Valida conteos mínimos directamente en PostGIS.",
    )
    parser.add_argument(
        "--check-local-fallback",
        action="store_true",
        help="Valida fallback CSV/GeoJSON sin usar DATABASE_URL.",
    )
    parser.add_argument("--database-url", default=None, help="DATABASE_URL para PostGIS.")
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def base_url(cli_value: str | None) -> str:
    load_dotenv()
    return (cli_value or os.getenv("API_BASE_URL") or DEFAULT_API_URL).rstrip("/")


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    return cli_value or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def get_json(
    api_url: str,
    path: str,
    timeout: float,
    token: str | None = None,
) -> dict[str, Any]:
    url = f"{api_url}{path}"
    headers = {"Authorization": f"Bearer {token}"} if token else None
    response = requests.get(url, headers=headers, timeout=timeout)
    check(response.ok, f"{path} devolvió HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    check(isinstance(data, dict), f"{path} no devolvió un objeto JSON")
    return data


def post_json(api_url: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = f"{api_url}{path}"
    response = requests.post(url, json=payload, timeout=timeout)
    check(response.ok, f"{path} devolvió HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    check(isinstance(data, dict), f"{path} no devolvió un objeto JSON")
    return data


def assert_source(data: dict[str, Any], expected: str, path: str) -> None:
    if expected == "any":
        return
    check(data.get("source") == expected, f"{path} usa source={data.get('source')}, esperado {expected}")


def assert_feature_collection(data: dict[str, Any], path: str) -> None:
    check(data.get("type") == "FeatureCollection", f"{path} no es FeatureCollection")
    features = data.get("features")
    check(isinstance(features, list), f"{path} no contiene lista features")
    check(len(features) > 0, f"{path} no contiene features")


def assert_items(data: dict[str, Any], path: str) -> list[dict[str, Any]]:
    items = data.get("items")
    check(isinstance(items, list), f"{path} no contiene lista items")
    check(len(items) > 0, f"{path} no contiene items")
    check(data.get("count", 0) > 0, f"{path} reporta count vacío")
    return items


def run_api_checks(api_url: str, expected_source: str, timeout: float) -> None:
    print(f"API: {api_url}")

    health = get_json(api_url, "/health", timeout)
    check(health.get("status") == "ok", "/health no devolvió status=ok")
    print("OK /health")

    auth = post_json(
        api_url,
        "/auth/login",
        {"email": "admin", "password": "admin123"},
        timeout,
    )
    check(auth.get("source") == "postgis", "/auth/login no usa source=postgis")
    check(auth.get("user", {}).get("view_mode") == "Admin", "/auth/login no abre vista Admin")
    admin_token = auth.get("access_token")
    check(isinstance(admin_token, str) and admin_token, "/auth/login no devolvió access_token")
    print("OK /auth/login admin")

    latest = get_json(api_url, "/rankings/latest?limit=5", timeout, admin_token)
    assert_source(latest, expected_source, "/rankings/latest")
    ranking_items = assert_items(latest, "/rankings/latest")
    required_ranking = {"parcela_id", "cultivo", "prioridad", "riesgo_actual"}
    check(
        required_ranking <= set(ranking_items[0]),
        f"/rankings/latest no contiene columnas mínimas: {sorted(required_ranking)}",
    )
    print(f"OK /rankings/latest source={latest.get('source')} count={latest.get('count')}")

    latest_geojson = get_json(api_url, "/rankings/latest/geojson", timeout, admin_token)
    assert_source(latest_geojson, expected_source, "/rankings/latest/geojson")
    assert_feature_collection(latest_geojson, "/rankings/latest/geojson")
    first_props = latest_geojson["features"][0].get("properties", {})
    check("parcela_id" in first_props, "/rankings/latest/geojson no incluye parcela_id")
    print(
        "OK /rankings/latest/geojson "
        f"features={len(latest_geojson['features'])} source={latest_geojson.get('source')}"
    )

    clientes = get_json(api_url, "/clientes", timeout, admin_token)
    assert_source(clientes, expected_source, "/clientes")
    cliente_items = assert_items(clientes, "/clientes")
    cliente_id = int(cliente_items[0]["cliente_id"])
    check("parcelas_asignadas" in cliente_items[0], "/clientes no incluye parcelas_asignadas")
    print(f"OK /clientes count={clientes.get('count')} primer_cliente={cliente_id}")

    admin_clientes = get_json(api_url, "/admin/clientes?limit=5", timeout, admin_token)
    assert_source(admin_clientes, expected_source, "/admin/clientes")
    assert_items(admin_clientes, "/admin/clientes")
    print(f"OK /admin/clientes count={admin_clientes.get('count')}")

    admin_parcelas = get_json(api_url, "/admin/parcelas?limit=1", timeout, admin_token)
    assert_source(admin_parcelas, expected_source, "/admin/parcelas")
    parcela_items = assert_items(admin_parcelas, "/admin/parcelas")
    parcela_id = int(parcela_items[0]["parcela_id"])
    check("cultivo_oficial" in parcela_items[0], "/admin/parcelas no incluye cultivo_oficial")
    print(f"OK /admin/parcelas count={admin_parcelas.get('count')} primera_parcela={parcela_id}")

    admin_parcela = get_json(api_url, f"/admin/parcelas/{parcela_id}", timeout, admin_token)
    assert_source(admin_parcela, expected_source, "/admin/parcelas/{id}")
    check("geometry" in admin_parcela.get("item", {}), "/admin/parcelas/{id} no incluye geometry")
    print(f"OK /admin/parcelas/{parcela_id}")

    disponibles = get_json(api_url, "/admin/parcelas/disponibles?limit=1", timeout, admin_token)
    assert_source(disponibles, expected_source, "/admin/parcelas/disponibles")
    check("items" in disponibles, "/admin/parcelas/disponibles no contiene items")
    print(f"OK /admin/parcelas/disponibles count={disponibles.get('count')}")

    admin_cliente_parcelas = get_json(
        api_url,
        f"/admin/clientes/{cliente_id}/parcelas",
        timeout,
        admin_token,
    )
    assert_source(admin_cliente_parcelas, expected_source, "/admin/clientes/{id}/parcelas")
    check(
        admin_cliente_parcelas.get("count", 0) > 0,
        "/admin/clientes/{id}/parcelas no contiene parcelas",
    )
    print(f"OK /admin/clientes/{cliente_id}/parcelas")

    cliente_geojson = get_json(
        api_url,
        f"/clientes/{cliente_id}/rankings/latest/geojson",
        timeout,
        admin_token,
    )
    assert_source(cliente_geojson, expected_source, "/clientes/{id}/rankings/latest/geojson")
    assert_feature_collection(cliente_geojson, "/clientes/{id}/rankings/latest/geojson")
    check(cliente_geojson.get("total_count", 0) > 0, "cliente sin parcelas en GeoJSON")
    print(f"OK /clientes/{cliente_id}/rankings/latest/geojson")

    regional = get_json(api_url, "/regional/um/latest?limit=5", timeout, admin_token)
    assert_source(regional, expected_source, "/regional/um/latest")
    um_items = assert_items(regional, "/regional/um/latest")
    um_id = int(um_items[0]["um_id"])
    check("ranking_um" in um_items[0], "/regional/um/latest no incluye ranking_um")
    print(f"OK /regional/um/latest count={regional.get('count')} primera_um={um_id}")

    regional_geojson = get_json(api_url, "/regional/um/latest/geojson", timeout, admin_token)
    assert_source(regional_geojson, expected_source, "/regional/um/latest/geojson")
    assert_feature_collection(regional_geojson, "/regional/um/latest/geojson")
    print(f"OK /regional/um/latest/geojson features={len(regional_geojson['features'])}")

    um_parcelas = get_json(
        api_url,
        f"/regional/um/{um_id}/parcelas/latest/geojson",
        timeout,
        admin_token,
    )
    assert_source(um_parcelas, expected_source, "/regional/um/{um_id}/parcelas/latest/geojson")
    assert_feature_collection(um_parcelas, "/regional/um/{um_id}/parcelas/latest/geojson")
    check(um_parcelas.get("total_count", 0) > 0, "UM sin parcelas en GeoJSON")
    print(f"OK /regional/um/{um_id}/parcelas/latest/geojson")


def run_postgis_checks(db_url: str) -> None:
    import psycopg

    checks = {
        "parcelas": "SELECT count(*) FROM parcelas",
        "ranking_hidrico_latest": "SELECT count(*) FROM ranking_hidrico_latest",
        "clientes": "SELECT count(*) FROM clientes WHERE activo = true",
        "cliente_parcela": "SELECT count(*) FROM cliente_parcela",
        "zonas_um": "SELECT count(*) FROM zonas_um",
        "parcela_um": "SELECT count(*) FROM parcela_um",
        "ranking_um_latest": "SELECT count(*) FROM ranking_um_latest",
        "usuarios": "SELECT count(*) FROM usuarios WHERE activo = true",
    }
    print("PostGIS: validando conteos mínimos")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for label, query in checks.items():
                cur.execute(query)
                value = int(cur.fetchone()[0])
                check(value > 0, f"PostGIS {label} no tiene registros")
                print(f"OK PostGIS {label}: {value}")
            cur.execute("SELECT postgis_version()")
            print(f"OK PostGIS version: {cur.fetchone()[0]}")


def run_local_fallback_checks() -> None:
    import backend.app.services.rankings as rankings

    original_database_url = rankings.database_url
    rankings.database_url = lambda: None
    try:
        latest = rankings.latest_ranking(limit=5)
        check(latest["source"] == "csv", "fallback latest_ranking no usa source=csv")
        check(latest["count"] == 5, "fallback latest_ranking no respeta limit=5")

        geojson = rankings.latest_geojson()
        check(geojson["source"] == "csv", "fallback latest_geojson no usa source=csv")
        check(len(geojson.get("features", [])) > 0, "fallback latest_geojson sin features")

        clientes = rankings.clientes()
        check(clientes["source"] == "csv", "fallback clientes no usa source=csv")
        check(clientes["count"] > 0, "fallback clientes sin registros")

        regional = rankings.regional_um_latest(limit=1)
        check(regional["source"] == "csv", "fallback regional no usa source=csv")
        check(regional["count"] == 1, "fallback regional no respeta limit=1")
    finally:
        rankings.database_url = original_database_url
    print("OK fallback local CSV/GeoJSON")


def main() -> int:
    args = parse_args()
    try:
        if not args.skip_api:
            run_api_checks(base_url(args.api_url), args.require_source, args.timeout)
        if args.check_postgis:
            run_postgis_checks(database_url(args.database_url))
        if args.check_local_fallback:
            run_local_fallback_checks()
    except Exception as exc:
        print(f"ERROR smoke test: {exc}", file=sys.stderr)
        return 1

    print("Smoke test operativo OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
