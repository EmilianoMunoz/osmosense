import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.pipeline.generar_ranking_hidrico import generar_ranking


INPUT_TEMPORAL = "backend/data/dataset_temporal_hidrico.csv"
MODEL_DIR = "backend/models/hidrico_regresion"
RANKING_CONFIG = "backend/models/ranking_hidrico_config.json"
PARCELAS_GEOJSON = "backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
OUTPUT_SAMPLE = "backend/data/parcelas/muestra_temporal_full_vid_olivo.geojson"
RANKINGS_DIR = "backend/data/rankings"
STATE_DIR = "backend/data/state"
LOGS_DIR = "backend/data/logs"
AUDIT_HISTORY_DIR = "backend/data/auditorias"
AUDIT_HISTORICAL_METRICS = "backend/data/auditoria_metricas_historicas.csv"
AUDIT_VECINOS_DETALLE = "backend/data/auditoria_vecinos_ranking_riesgo_actual.csv"
AUDIT_VECINOS_RESUMEN = "backend/data/auditoria_vecinos_ranking_riesgo_actual_resumen.csv"
AUDIT_VECINOS_GEOJSON = "backend/data/auditoria_vecinos_ranking_riesgo_actual.geojson"
AUDIT_TEMPORAL_DETALLE = "backend/data/auditoria_outliers_temporales.csv"
AUDIT_TEMPORAL_RESUMEN = "backend/data/auditoria_outliers_temporales_resumen.csv"
AUDIT_RUIDO_DETALLE = "backend/data/auditoria_ruido_puntual_detalle.csv"
AUDIT_RUIDO_RESUMEN = "backend/data/auditoria_ruido_puntual_resumen.csv"
AUDIT_RUIDO_GEOJSON = "backend/data/auditoria_ruido_puntual_detalle.geojson"
ZONIFICACION_GEOJSON = "backend/data/zonificacion/regional_dgi_san_rafael.geojson"
ZONIFICACION_OUT_DIR = "backend/data/zonificacion"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orquesta el pipeline hidrico local/cloud."
    )
    parser.add_argument("--mode", choices=["local", "cloud"], default="local")
    parser.add_argument("--input", default=INPUT_TEMPORAL)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--ranking-config", default=RANKING_CONFIG)
    parser.add_argument("--parcelas", default=PARCELAS_GEOJSON)
    parser.add_argument("--rankings-dir", default=RANKINGS_DIR)
    parser.add_argument("--state-dir", default=STATE_DIR)
    parser.add_argument("--logs-dir", default=LOGS_DIR)
    parser.add_argument("--audit-history-dir", default=AUDIT_HISTORY_DIR)
    parser.add_argument("--fecha", default=None, help="Fecha a rankear. Default: ultima disponible.")
    parser.add_argument(
        "--max-reading-age-days",
        type=int,
        default=15,
        help=(
            "Antiguedad maxima de observacion valida por parcela para ranking latest."
        ),
    )
    parser.add_argument("--update-sentinel", action="store_true")
    parser.add_argument("--extract-start-date", default="2023-01-01")
    parser.add_argument("--extract-end-date", default=None)
    parser.add_argument("--extract-chunk-size", type=int, default=500)
    parser.add_argument("--extract-window-days", type=int, default=5)
    parser.add_argument("--extract-step-days", type=int, default=5)
    parser.add_argument("--extract-cloud-threshold", type=float, default=35.0)
    parser.add_argument("--extract-output-sample", default=OUTPUT_SAMPLE)
    parser.add_argument(
        "--parcel-source",
        choices=["geojson", "postgis"],
        default="geojson",
        help="Fuente de parcelas objetivo para la extracción Sentinel.",
    )
    parser.add_argument(
        "--update-recent-window",
        action="store_true",
        help=(
            "Al actualizar Sentinel, extrae todas las parcelas objetivo para una "
            "ventana reciente en vez de continuar todo el histórico."
        ),
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=10,
        help="Cantidad de dias hacia atras a cubrir con --update-recent-window.",
    )
    parser.add_argument(
        "--resolve-latest-valid-date",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "En modo ventana reciente, busca hacia atras la ultima ventana "
            "Sentinel con imagenes validas y la usa como fecha objetivo."
        ),
    )
    parser.add_argument(
        "--latest-lookback-days",
        type=int,
        default=30,
        help="Dias maximos hacia atras para buscar la ultima ventana Sentinel valida.",
    )
    parser.add_argument(
        "--latest-min-images",
        type=int,
        default=1,
        help="Minimo de imagenes Sentinel requeridas para aceptar una ventana.",
    )
    parser.add_argument(
        "--load-postgis",
        action="store_true",
        help="Carga el ranking generado en PostGIS usando DATABASE_URL.",
    )
    parser.add_argument(
        "--update-zonificacion-um",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Regenera parcelas_um, um_con_cultivos y ranking_um_latest despues del ranking.",
    )
    parser.add_argument(
        "--run-quality-audits",
        action="store_true",
        help="Ejecuta auditorias espacial y temporal despues de generar el ranking.",
    )
    parser.add_argument(
        "--backfill-outlier-history",
        action="store_true",
        help=(
            "Luego de la auditoria espacial, extrae historial reciente solo para "
            "outliers antes de ejecutar la auditoria temporal."
        ),
    )
    parser.add_argument(
        "--backfill-days",
        type=int,
        default=45,
        help="Dias hacia atras para backfill de historial reciente de outliers.",
    )
    parser.add_argument(
        "--quality-score-column",
        default="riesgo_actual",
        help="Columna del ranking usada por la auditoria espacial de vecinos.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL Postgres/PostGIS. Si se omite usa DATABASE_URL del entorno.",
    )
    parser.add_argument(
        "--skip-if-no-new-date",
        action="store_true",
        help="Si se actualiza Sentinel/GEE y la ultima fecha no cambia, omite el ranking.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log(message: str, log_path: Path) -> None:
    line = f"{utc_now()} {message}"
    print(line, flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run_command(command: list[str], log_path: Path, dry_run: bool) -> None:
    log("CMD " + " ".join(command), log_path)
    if dry_run:
        return

    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        for line in result.stdout.rstrip().splitlines():
            log("OUT " + line, log_path)
    if result.stderr:
        for line in result.stderr.rstrip().splitlines():
            log("ERR " + line, log_path)
    if result.returncode != 0:
        raise RuntimeError(f"Comando fallo con exit code {result.returncode}: {' '.join(command)}")


def recent_window_bounds(
    end_date: str,
    recent_days: int,
    window_days: int,
) -> tuple[str, str]:
    end = datetime.fromisoformat(end_date).date()
    first_window_start = end - timedelta(days=recent_days + window_days)
    last_window_start = end - timedelta(days=window_days)
    return first_window_start.isoformat(), last_window_start.isoformat()


def resolver_latest_valid_date(args: argparse.Namespace, log_path: Path) -> str:
    from backend.app.core.gee import inicializar_gee
    from backend.app.core.region import region_san_rafael_ee
    from backend.app.services.images import obtener_imagenes_sentinel

    inicializar_gee()
    region = region_san_rafael_ee()
    end = date.fromisoformat(args.extract_end_date or datetime.now().date().isoformat())

    for offset in range(0, args.latest_lookback_days + 1):
        candidate_end = end - timedelta(days=offset)
        candidate_start = candidate_end - timedelta(days=args.extract_window_days)
        coleccion = obtener_imagenes_sentinel(
            region,
            candidate_start.isoformat(),
            candidate_end.isoformat(),
            umbral_nubosidad=args.extract_cloud_threshold,
        )
        image_count = int(coleccion.size().getInfo())
        log(
            "Latest Sentinel candidato: "
            f"{candidate_start.isoformat()} -> {candidate_end.isoformat()} "
            f"imagenes={image_count}",
            log_path,
        )
        if image_count >= args.latest_min_images:
            return candidate_end.isoformat()

    raise RuntimeError(
        "No se encontro ventana Sentinel valida en los ultimos "
        f"{args.latest_lookback_days} dias."
    )


def actualizar_sentinel(args: argparse.Namespace, log_path: Path) -> None:
    end_date = args.extract_end_date or datetime.now().date().isoformat()
    target_end_date = end_date
    if (
        args.update_recent_window
        and args.resolve_latest_valid_date
        and not args.dry_run
    ):
        target_end_date = resolver_latest_valid_date(args, log_path)
    elif args.update_recent_window and args.resolve_latest_valid_date and args.dry_run:
        log(
            "Dry-run: no se consulta GEE para resolver latest valido; "
            f"se usa target_end={target_end_date}",
            log_path,
        )

    if args.update_recent_window:
        start_date, extraction_end_date = recent_window_bounds(
            target_end_date,
            args.recent_days,
            args.extract_window_days,
        )
    else:
        start_date = args.extract_start_date
        extraction_end_date = end_date

    command = [
        sys.executable,
        "backend/scripts/pipeline/generar_dataset_temporal_hidrico.py",
        "--output",
        args.input,
        "--output-sample",
        args.extract_output_sample,
        "--start-date",
        start_date,
        "--end-date",
        extraction_end_date,
        "--step-days",
        str(args.extract_step_days),
        "--window-days",
        str(args.extract_window_days),
        "--chunk-size",
        str(args.extract_chunk_size),
        "--cloud-threshold",
        str(args.extract_cloud_threshold),
        "--parcel-source",
        args.parcel_source,
        "--resume",
    ]
    if args.parcel_source == "postgis" and args.database_url:
        command.extend(["--database-url", args.database_url])
    if args.update_recent_window:
        command.append("--all-target-parcels")
    else:
        command.extend(["--reuse-sample", "--resume-from-max-date"])

    log(
        "Actualizacion Sentinel configurada: "
        f"start={start_date} end={extraction_end_date} "
        f"target_end={target_end_date} recent_window={args.update_recent_window} "
        f"resolve_latest_valid={args.resolve_latest_valid_date}",
        log_path,
    )
    run_command(command, log_path, args.dry_run)


def ultima_fecha_dataset(path: str | Path) -> str | None:
    dataset_path = Path(path)
    if not dataset_path.exists():
        return None

    df = pd.read_csv(dataset_path, usecols=["fecha"])
    if df.empty:
        return None
    return str(pd.to_datetime(df["fecha"]).max().date())


def path_salida(rankings_dir: Path, fecha: str) -> Path:
    return rankings_dir / f"ranking_hidrico_{fecha}.csv"


def guardar_estado(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "pipeline_hidrico_state.json"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def ejecutar_ranking(args: argparse.Namespace, log_path: Path) -> dict:
    df_temporal = pd.read_csv(args.input)
    ranking = generar_ranking(
        df_temporal,
        Path(args.model_dir),
        args.fecha,
        args.ranking_config,
        args.parcelas,
        args.max_reading_age_days,
    )
    fecha_usada = ranking["fecha_actual"].iloc[0]

    rankings_dir = Path(args.rankings_dir)
    rankings_dir.mkdir(parents=True, exist_ok=True)
    output_path = path_salida(rankings_dir, fecha_usada)
    latest_path = rankings_dir / "ranking_hidrico_latest.csv"

    if not args.dry_run:
        ranking.to_csv(output_path, index=False)
        ranking.to_csv(latest_path, index=False)

    state = {
        "mode": args.mode,
        "last_run_utc": utc_now(),
        "skipped": False,
        "fecha_rankeada": fecha_usada,
        "input_temporal": args.input,
        "model_dir": args.model_dir,
        "ranking_config": args.ranking_config,
        "parcelas_geojson": args.parcelas,
        "ranking_output": str(output_path),
        "ranking_latest": str(latest_path),
        "parcelas": int(len(ranking)),
        "distribucion_cultivo": ranking["cultivo"].value_counts().to_dict(),
        "distribucion_prioridad": ranking["prioridad"].value_counts().to_dict(),
    }
    if not args.dry_run:
        guardar_estado(Path(args.state_dir), state)

    log(f"Ranking generado: {output_path}", log_path)
    log(f"Fecha rankeada: {fecha_usada}", log_path)
    log(f"Parcelas: {len(ranking)}", log_path)
    log(f"Prioridades: {state['distribucion_prioridad']}", log_path)
    return state


def ejecutar_zonificacion_um(
    args: argparse.Namespace,
    state: dict,
    log_path: Path,
) -> dict:
    command = [
        sys.executable,
        "backend/scripts/zonificacion/cruzar_parcelas_zonificacion_um.py",
        "--zonificacion",
        ZONIFICACION_GEOJSON,
        "--parcelas",
        args.parcelas,
        "--ranking",
        state["ranking_latest"],
        "--out-dir",
        ZONIFICACION_OUT_DIR,
    ]
    run_command(command, log_path, args.dry_run)
    zonificacion_state = {
        "parcelas_um": _read_csv_summary(Path(ZONIFICACION_OUT_DIR) / "parcelas_um.csv"),
        "ranking_um_latest": _read_csv_summary(
            Path(ZONIFICACION_OUT_DIR) / "ranking_um_latest.csv"
        ),
        "um_con_cultivos": {
            "path": str(Path(ZONIFICACION_OUT_DIR) / "um_con_cultivos.geojson"),
            "exists": (Path(ZONIFICACION_OUT_DIR) / "um_con_cultivos.geojson").exists(),
        },
    }
    state["zonificacion_um"] = zonificacion_state
    if not args.dry_run:
        guardar_estado(Path(args.state_dir), state)
    return state


def _read_csv_summary(path: str | Path) -> dict:
    csv_path = Path(path)
    if not csv_path.exists():
        return {"path": str(csv_path), "exists": False}
    df = pd.read_csv(csv_path)
    return {"path": str(csv_path), "exists": True, "rows": int(len(df))}


def guardar_snapshot_auditorias(
    args: argparse.Namespace,
    state: dict,
    log_path: Path,
) -> dict:
    fecha = str(state["fecha_rankeada"])
    snapshot_dir = Path(args.audit_history_dir) / fecha
    files = {
        "vecinos_detalle": AUDIT_VECINOS_DETALLE,
        "vecinos_resumen": AUDIT_VECINOS_RESUMEN,
        "vecinos_geojson": AUDIT_VECINOS_GEOJSON,
        "temporal_detalle": AUDIT_TEMPORAL_DETALLE,
        "temporal_resumen": AUDIT_TEMPORAL_RESUMEN,
        "ruido_detalle": AUDIT_RUIDO_DETALLE,
        "ruido_resumen": AUDIT_RUIDO_RESUMEN,
        "ruido_geojson": AUDIT_RUIDO_GEOJSON,
    }

    if args.dry_run:
        log(f"Dry-run: snapshot auditorias se guardaria en {snapshot_dir}", log_path)
        return {
            "path": str(snapshot_dir),
            "exists": False,
            "files": list(files),
        }

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    copied = {}
    for name, source in files.items():
        source_path = Path(source)
        if not source_path.exists():
            copied[name] = {"source": str(source_path), "copied": False}
            continue

        target = snapshot_dir / source_path.name
        shutil.copy2(source_path, target)
        copied[name] = {
            "source": str(source_path),
            "target": str(target),
            "copied": True,
        }

    metadata = {
        "fecha_rankeada": fecha,
        "created_utc": utc_now(),
        "ranking_latest": state.get("ranking_latest"),
        "score_column": args.quality_score_column,
        "files": copied,
    }
    metadata_path = snapshot_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    log(f"Snapshot auditorias guardado: {snapshot_dir}", log_path)
    return {
        "path": str(snapshot_dir),
        "exists": True,
        "files": copied,
        "metadata": str(metadata_path),
    }


def generar_metricas_historicas_auditorias(
    args: argparse.Namespace,
    state: dict,
    log_path: Path,
) -> dict:
    command = [
        sys.executable,
        "backend/scripts/audit/generar_metricas_historicas_auditorias.py",
        "--input-dir",
        args.audit_history_dir,
        "--output",
        AUDIT_HISTORICAL_METRICS,
        "--reference-date",
        str(state["fecha_rankeada"]),
        "--window-days",
        "30",
    ]
    run_command(command, log_path, args.dry_run)
    return _read_csv_summary(AUDIT_HISTORICAL_METRICS)


def ejecutar_auditorias_calidad(
    args: argparse.Namespace,
    state: dict,
    log_path: Path,
) -> dict:
    command_vecinos = [
        sys.executable,
        "backend/scripts/audit/auditar_vecinos_ranking.py",
        "--ranking",
        state["ranking_latest"],
        "--parcelas",
        args.parcelas,
        "--score-column",
        args.quality_score_column,
        "--output-detalle",
        AUDIT_VECINOS_DETALLE,
        "--output-resumen",
        AUDIT_VECINOS_RESUMEN,
        "--output-geojson",
        AUDIT_VECINOS_GEOJSON,
    ]
    run_command(command_vecinos, log_path, args.dry_run)

    if args.backfill_outlier_history:
        ejecutar_backfill_outlier_history(args, state, log_path)

    command_temporal = [
        sys.executable,
        "backend/scripts/audit/auditar_outliers_temporales.py",
        "--temporal",
        args.input,
        "--outliers",
        AUDIT_VECINOS_DETALLE,
        "--output-detalle",
        AUDIT_TEMPORAL_DETALLE,
        "--output-resumen",
        AUDIT_TEMPORAL_RESUMEN,
    ]
    run_command(command_temporal, log_path, args.dry_run)

    command_ruido = [
        sys.executable,
        "backend/scripts/audit/auditar_ruido_puntual.py",
        "--input",
        AUDIT_TEMPORAL_DETALLE,
        "--parcelas",
        args.parcelas,
        "--output-detalle",
        AUDIT_RUIDO_DETALLE,
        "--output-resumen",
        AUDIT_RUIDO_RESUMEN,
        "--output-geojson",
        AUDIT_RUIDO_GEOJSON,
    ]
    run_command(command_ruido, log_path, args.dry_run)

    snapshot = guardar_snapshot_auditorias(args, state, log_path)
    metricas_historicas = generar_metricas_historicas_auditorias(
        args,
        state,
        log_path,
    )

    quality_state = {
        "score_column": args.quality_score_column,
        "snapshot": snapshot,
        "metricas_historicas": metricas_historicas,
        "vecinos_detalle": _read_csv_summary(AUDIT_VECINOS_DETALLE),
        "vecinos_resumen": _read_csv_summary(AUDIT_VECINOS_RESUMEN),
        "temporal_detalle": _read_csv_summary(AUDIT_TEMPORAL_DETALLE),
        "temporal_resumen": _read_csv_summary(AUDIT_TEMPORAL_RESUMEN),
        "ruido_detalle": _read_csv_summary(AUDIT_RUIDO_DETALLE),
        "ruido_resumen": _read_csv_summary(AUDIT_RUIDO_RESUMEN),
    }
    state["quality_audits"] = quality_state
    if not args.dry_run:
        guardar_estado(Path(args.state_dir), state)
    return state


def ejecutar_backfill_outlier_history(
    args: argparse.Namespace,
    state: dict,
    log_path: Path,
) -> None:
    vecinos_path = Path(AUDIT_VECINOS_DETALLE)
    if not vecinos_path.exists():
        if args.dry_run:
            log(
                "Dry-run: no se genera CSV de outliers para backfill; "
                f"se usaria {vecinos_path}",
                log_path,
            )
            return
        raise FileNotFoundError(
            f"No existe auditoria espacial para backfill: {vecinos_path}"
        )

    vecinos = pd.read_csv(vecinos_path)
    required = {
        "parcela_id",
        "outlier_espacial",
        "abs_riesgo_actual_vs_neighbor_median",
    }
    missing = sorted(required - set(vecinos.columns))
    if missing:
        raise RuntimeError(
            f"No se puede generar backfill; faltan columnas en {vecinos_path}: {missing}"
        )

    outliers = vecinos[
        vecinos["outlier_espacial"].astype(bool)
        & (vecinos["abs_riesgo_actual_vs_neighbor_median"] >= 35.0)
    ][["parcela_id"]].drop_duplicates()

    if outliers.empty:
        log("Backfill omitido: no hay outliers espaciales.", log_path)
        return

    state_dir = Path(args.state_dir)
    ids_path = state_dir / "backfill_outlier_ids.csv"
    if not args.dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
        outliers.to_csv(ids_path, index=False)

    fecha_latest = date.fromisoformat(str(state["fecha_rankeada"]))
    start_date = (fecha_latest - timedelta(days=args.backfill_days)).isoformat()
    end_date = (fecha_latest - timedelta(days=args.extract_window_days)).isoformat()

    log(
        "Backfill outliers configurado: "
        f"outliers={len(outliers)} start={start_date} end={end_date} "
        f"step={args.extract_step_days} window={args.extract_window_days}",
        log_path,
    )

    command = [
        sys.executable,
        "backend/scripts/pipeline/generar_dataset_temporal_hidrico.py",
        "--output",
        args.input,
        "--output-sample",
        args.extract_output_sample,
        "--start-date",
        start_date,
        "--end-date",
        end_date,
        "--step-days",
        str(args.extract_step_days),
        "--window-days",
        str(args.extract_window_days),
        "--chunk-size",
        str(args.extract_chunk_size),
        "--cloud-threshold",
        str(args.extract_cloud_threshold),
        "--parcel-source",
        args.parcel_source,
        "--all-target-parcels",
        "--target-ids-csv",
        str(ids_path),
        "--resume",
    ]
    if args.parcel_source == "postgis" and args.database_url:
        command.extend(["--database-url", args.database_url])
    run_command(command, log_path, args.dry_run)


def cargar_ranking_postgis(args: argparse.Namespace, state: dict, log_path: Path) -> None:
    command = [
        sys.executable,
        "backend/scripts/postgis/cargar_ranking_postgis.py",
        "--input",
        state["ranking_latest"],
        "--model-dir",
        args.model_dir,
        "--ranking-config",
        args.ranking_config,
        "--pipeline-run-id",
        state["last_run_utc"],
    ]
    if args.database_url:
        command.extend(["--database-url", args.database_url])
    if args.dry_run:
        command.append("--dry-run")

    run_command(command, log_path, args.dry_run)


def cargar_zonificacion_postgis(args: argparse.Namespace, state: dict, log_path: Path) -> None:
    command = [
        sys.executable,
        "backend/scripts/postgis/cargar_zonificacion_um_postgis.py",
        "--zonas",
        str(Path(ZONIFICACION_OUT_DIR) / "um_con_cultivos.geojson"),
        "--parcelas-um",
        str(Path(ZONIFICACION_OUT_DIR) / "parcelas_um.csv"),
        "--ranking-um",
        str(Path(ZONIFICACION_OUT_DIR) / "ranking_um_latest.csv"),
        "--pipeline-run-id",
        state["last_run_utc"],
    ]
    if args.database_url:
        command.extend(["--database-url", args.database_url])
    if args.dry_run:
        command.append("--dry-run")

    run_command(command, log_path, args.dry_run)


def main() -> None:
    args = parse_args()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(args.logs_dir) / f"pipeline_hidrico_{run_id}.log"

    log(f"Inicio pipeline hidrico mode={args.mode}", log_path)
    log(f"Dry run: {args.dry_run}", log_path)
    quality_enabled = args.run_quality_audits or args.backfill_outlier_history
    total_steps = (
        2
        + int(args.update_zonificacion_um)
        + int(quality_enabled)
        + int(args.load_postgis)
    )

    fecha_antes = ultima_fecha_dataset(args.input)
    log(f"Ultima fecha antes de actualizar: {fecha_antes}", log_path)

    if args.update_sentinel:
        log(f"Paso 1/{total_steps}: actualizar Sentinel/GEE", log_path)
        actualizar_sentinel(args, log_path)
    else:
        log(f"Paso 1/{total_steps}: actualizar Sentinel/GEE omitido", log_path)

    fecha_despues = ultima_fecha_dataset(args.input)
    log(f"Ultima fecha despues de actualizar: {fecha_despues}", log_path)

    if (
        args.update_sentinel
        and args.skip_if_no_new_date
        and fecha_antes is not None
        and fecha_despues == fecha_antes
    ):
        state = {
            "mode": args.mode,
            "last_run_utc": utc_now(),
            "input_temporal": args.input,
            "fecha_dataset": fecha_despues,
            "fecha_dataset_antes": fecha_antes,
            "fecha_dataset_despues": fecha_despues,
            "log_path": str(log_path),
            "update_sentinel": args.update_sentinel,
            "load_postgis": args.load_postgis,
            "skipped": True,
            "reason": "sin_fecha_nueva",
        }
        if not args.dry_run:
            guardar_estado(Path(args.state_dir), state)
        log("Pipeline omitido: no ingreso una fecha nueva valida", log_path)
        print(json.dumps(state, indent=2), flush=True)
        return

    log(f"Paso 2/{total_steps}: generar ranking", log_path)
    state = ejecutar_ranking(args, log_path)
    state["fecha_dataset_antes"] = fecha_antes
    state["fecha_dataset_despues"] = fecha_despues
    state["log_path"] = str(log_path)
    state["update_sentinel"] = args.update_sentinel
    state["load_postgis"] = args.load_postgis
    if not args.dry_run:
        guardar_estado(Path(args.state_dir), state)

    step = 3
    if args.update_zonificacion_um:
        log(f"Paso {step}/{total_steps}: regenerar ranking regional UM", log_path)
        state = ejecutar_zonificacion_um(args, state, log_path)
        step += 1
    else:
        log("Zonificacion UM omitida", log_path)

    if quality_enabled:
        log(f"Paso {step}/{total_steps}: auditar calidad del ranking", log_path)
        state = ejecutar_auditorias_calidad(args, state, log_path)
        step += 1
    else:
        log("Auditorias de calidad omitidas", log_path)

    if args.load_postgis:
        log(f"Paso {step}/{total_steps}: cargar ranking en PostGIS", log_path)
        cargar_ranking_postgis(args, state, log_path)
        if args.update_zonificacion_um:
            cargar_zonificacion_postgis(args, state, log_path)
        state["postgis_loaded"] = not args.dry_run
        if not args.dry_run:
            guardar_estado(Path(args.state_dir), state)
    else:
        log("Carga PostGIS omitida", log_path)

    log("Pipeline finalizado correctamente", log_path)
    print(json.dumps(state, indent=2), flush=True)


if __name__ == "__main__":
    main()
