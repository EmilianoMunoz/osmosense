import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


INPUT_AUDIT_HISTORY_DIR = "backend/data/auditorias"
OUTPUT_METRICAS = "backend/data/auditoria_metricas_historicas.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera metricas historicas por parcela a partir de snapshots de auditorias."
    )
    parser.add_argument("--input-dir", default=INPUT_AUDIT_HISTORY_DIR)
    parser.add_argument("--output", default=OUTPUT_METRICAS)
    parser.add_argument(
        "--reference-date",
        default=None,
        help="Fecha de referencia YYYY-MM-DD. Default: ultima fecha disponible.",
    )
    parser.add_argument("--window-days", type=int, default=30)
    return parser.parse_args()


def snapshot_dirs(input_dir: str | Path) -> list[Path]:
    root = Path(input_dir)
    if not root.exists():
        return []

    dirs = []
    for path in root.iterdir():
        if not path.is_dir():
            continue
        try:
            date.fromisoformat(path.name)
        except ValueError:
            continue
        dirs.append(path)
    return sorted(dirs, key=lambda item: item.name)


def read_snapshot_csv(path: Path, fecha: str, kind: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty or "parcela_id" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["parcela_id"] = df["parcela_id"].astype(int)
    df["fecha_ranking"] = pd.to_datetime(fecha)
    df["snapshot_kind"] = kind
    return df


def cargar_eventos(input_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    outlier_frames = []
    ruido_frames = []

    for folder in snapshot_dirs(input_dir):
        fecha = folder.name
        outliers = read_snapshot_csv(
            folder / "auditoria_outliers_temporales.csv",
            fecha,
            "outliers_temporales",
        )
        if not outliers.empty:
            outlier_frames.append(outliers)

        ruido = read_snapshot_csv(
            folder / "auditoria_ruido_puntual_detalle.csv",
            fecha,
            "ruido_puntual",
        )
        if not ruido.empty:
            ruido_frames.append(ruido)

    outliers_df = (
        pd.concat(outlier_frames, ignore_index=True)
        if outlier_frames
        else pd.DataFrame()
    )
    ruido_df = (
        pd.concat(ruido_frames, ignore_index=True)
        if ruido_frames
        else pd.DataFrame()
    )
    return outliers_df, ruido_df


def filtrar_ventana(df: pd.DataFrame, reference_date: pd.Timestamp, window_days: int) -> pd.DataFrame:
    if df.empty:
        return df
    start = reference_date - pd.Timedelta(days=window_days)
    return df[
        (df["fecha_ranking"] >= start)
        & (df["fecha_ranking"] <= reference_date)
    ].copy()


def agregar_metricas_eventos(
    base: pd.DataFrame,
    events: pd.DataFrame,
    prefix: str,
    condition_col: str | None = None,
    condition_value: str | None = None,
) -> pd.DataFrame:
    if events.empty:
        base[f"{prefix}_count_30d"] = 0
        base[f"ultima_fecha_{prefix}"] = pd.NaT
        base[f"dias_desde_ultimo_{prefix}"] = np.nan
        return base

    filtered = events.copy()
    if condition_col and condition_col in filtered.columns:
        filtered = filtered[filtered[condition_col] == condition_value].copy()

    if filtered.empty:
        base[f"{prefix}_count_30d"] = 0
        base[f"ultima_fecha_{prefix}"] = pd.NaT
        base[f"dias_desde_ultimo_{prefix}"] = np.nan
        return base

    grouped = filtered.groupby("parcela_id")["fecha_ranking"].agg(
        **{
            f"{prefix}_count_30d": "count",
            f"ultima_fecha_{prefix}": "max",
        }
    )
    base = base.join(grouped, how="left")
    base[f"{prefix}_count_30d"] = base[f"{prefix}_count_30d"].fillna(0).astype(int)
    return base


def generar_metricas(
    input_dir: str | Path,
    reference_date: str | None,
    window_days: int,
) -> pd.DataFrame:
    outliers, ruido = cargar_eventos(input_dir)
    if outliers.empty and ruido.empty:
        raise RuntimeError(f"No hay snapshots de auditorias en {input_dir}.")

    available_dates = []
    for df in [outliers, ruido]:
        if not df.empty:
            available_dates.extend(df["fecha_ranking"].dropna().tolist())
    ref = pd.Timestamp(reference_date) if reference_date else max(available_dates)

    outliers_window = filtrar_ventana(outliers, ref, window_days)
    ruido_window = filtrar_ventana(ruido, ref, window_days)

    ids = set()
    if not outliers_window.empty:
        ids.update(outliers_window["parcela_id"].astype(int).tolist())
    if not ruido_window.empty:
        ids.update(ruido_window["parcela_id"].astype(int).tolist())

    base = pd.DataFrame({"parcela_id": sorted(ids)}).set_index("parcela_id")
    base = agregar_metricas_eventos(base, outliers_window, "outlier")
    base = agregar_metricas_eventos(
        base,
        outliers_window,
        "persistente",
        "persistencia_temporal",
        "persistente",
    )
    base = agregar_metricas_eventos(base, ruido_window, "ruido")

    for prefix in ["outlier", "persistente", "ruido"]:
        fecha_col = f"ultima_fecha_{prefix}"
        dias_col = f"dias_desde_ultimo_{prefix}"
        if fecha_col not in base.columns:
            base[fecha_col] = pd.NaT
        base[dias_col] = (ref - pd.to_datetime(base[fecha_col])).dt.days

    base = base.reset_index()
    base["fecha_referencia"] = ref.date().isoformat()
    base["ventana_dias"] = window_days

    date_cols = [
        "ultima_fecha_outlier",
        "ultima_fecha_persistente",
        "ultima_fecha_ruido",
    ]
    for col in date_cols:
        base[col] = pd.to_datetime(base[col]).dt.strftime("%Y-%m-%d")
        base[col] = base[col].replace("NaT", np.nan)

    ordered_cols = [
        "parcela_id",
        "fecha_referencia",
        "ventana_dias",
        "outlier_count_30d",
        "persistente_count_30d",
        "ruido_count_30d",
        "ultima_fecha_outlier",
        "ultima_fecha_persistente",
        "ultima_fecha_ruido",
        "dias_desde_ultimo_outlier",
        "dias_desde_ultimo_persistente",
        "dias_desde_ultimo_ruido",
    ]
    return base[ordered_cols].sort_values(
        ["outlier_count_30d", "persistente_count_30d", "ruido_count_30d"],
        ascending=False,
    )


def main() -> None:
    args = parse_args()
    metricas = generar_metricas(args.input_dir, args.reference_date, args.window_days)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    metricas.to_csv(output, index=False)

    print("=== Metricas historicas de auditorias ===")
    print("Input:", args.input_dir)
    print("Output:", output)
    print("Shape:", metricas.shape)
    print("Fecha referencia:", metricas["fecha_referencia"].iloc[0])
    print("Ventana dias:", metricas["ventana_dias"].iloc[0])
    print("Parcelas con outlier:", int((metricas["outlier_count_30d"] > 0).sum()))
    print("Parcelas con persistencia:", int((metricas["persistente_count_30d"] > 0).sum()))
    print("Parcelas con ruido:", int((metricas["ruido_count_30d"] > 0).sum()))


if __name__ == "__main__":
    main()
