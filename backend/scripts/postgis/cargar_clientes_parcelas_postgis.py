import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


INPUT_CLIENTES = "backend/data/clientes/clientes.csv"
INPUT_RELACIONES = "backend/data/clientes/cliente_parcela.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga clientes y relación cliente-parcela en PostGIS."
    )
    parser.add_argument("--clientes", default=INPUT_CLIENTES)
    parser.add_argument("--cliente-parcela", default=INPUT_RELACIONES)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    value = cli_value or os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("Configurar DATABASE_URL o pasar --database-url.")
    return value


def read_clientes(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"cliente_id", "nombre", "tipo"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Columnas faltantes en {path}: {missing}")

    df = df.copy()
    df["cliente_id"] = pd.to_numeric(df["cliente_id"], errors="raise").astype(int)
    if "descripcion" not in df.columns:
        df["descripcion"] = None
    if "activo" not in df.columns:
        df["activo"] = True
    return df[["cliente_id", "nombre", "tipo", "descripcion", "activo"]]


def read_relaciones(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"cliente_id", "parcela_id"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Columnas faltantes en {path}: {missing}")

    df = df.copy()
    df["cliente_id"] = pd.to_numeric(df["cliente_id"], errors="raise").astype(int)
    df["parcela_id"] = pd.to_numeric(df["parcela_id"], errors="raise").astype(int)
    if "etiqueta" not in df.columns:
        df["etiqueta"] = None
    return df[["cliente_id", "parcela_id", "etiqueta"]].drop_duplicates(
        ["cliente_id", "parcela_id"],
        keep="first",
    )


def main() -> None:
    args = parse_args()
    clientes = read_clientes(args.clientes)
    relaciones = read_relaciones(args.cliente_parcela)

    cliente_ids = set(clientes["cliente_id"])
    invalid = sorted(set(relaciones["cliente_id"]) - cliente_ids)
    if invalid:
        raise RuntimeError(f"Relaciones con cliente_id inexistente en CSV: {invalid}")

    print("=== Carga clientes PostGIS ===")
    print("Clientes:", len(clientes))
    print("Relaciones cliente-parcela:", len(relaciones))
    print("Dry run:", args.dry_run)
    if args.dry_run:
        return

    import psycopg

    upsert_clientes = """
        INSERT INTO clientes (cliente_id, nombre, tipo, descripcion, activo)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (cliente_id) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            tipo = EXCLUDED.tipo,
            descripcion = EXCLUDED.descripcion,
            activo = EXCLUDED.activo,
            updated_at = now()
    """
    upsert_relaciones = """
        INSERT INTO cliente_parcela (cliente_id, parcela_id, etiqueta)
        VALUES (%s, %s, %s)
        ON CONFLICT (cliente_id, parcela_id) DO UPDATE SET
            etiqueta = EXCLUDED.etiqueta
    """

    with psycopg.connect(database_url(args.database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT parcela_id FROM parcelas")
            parcelas_existentes = {int(row[0]) for row in cur.fetchall()}
            relaciones_validas = relaciones[
                relaciones["parcela_id"].isin(parcelas_existentes)
            ].copy()
            relaciones_invalidas = relaciones[
                ~relaciones["parcela_id"].isin(parcelas_existentes)
            ].copy()
            if not relaciones_invalidas.empty:
                print(
                    "Relaciones omitidas por parcela inexistente:",
                    len(relaciones_invalidas),
                )
                print(
                    relaciones_invalidas[["cliente_id", "parcela_id", "etiqueta"]]
                    .to_string(index=False)
                )
            cur.executemany(
                upsert_clientes,
                [
                    (
                        int(row.cliente_id),
                        str(row.nombre),
                        str(row.tipo),
                        None if pd.isna(row.descripcion) else str(row.descripcion),
                        bool(row.activo),
                    )
                    for row in clientes.itertuples(index=False)
                ],
            )
            cur.executemany(
                upsert_relaciones,
                [
                    (
                        int(row.cliente_id),
                        int(row.parcela_id),
                        None if pd.isna(row.etiqueta) else str(row.etiqueta),
                    )
                    for row in relaciones_validas.itertuples(index=False)
                ],
            )
        conn.commit()

    print("Carga finalizada.")


if __name__ == "__main__":
    main()
