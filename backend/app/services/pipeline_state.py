from __future__ import annotations

import json
import os
from decimal import Decimal
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv


PIPELINE_STATE_PATH = Path("backend/data/state/pipeline_hidrico_state.json")
DEFAULT_PROCESSING_STALE_HOURS = 6.0


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _ranking_summary(path: str | None) -> dict[str, Any]:
    if not path:
        return {"exists": False}

    ranking_path = Path(path)
    if not ranking_path.exists():
        return {"path": str(ranking_path), "exists": False}

    summary_columns = {
        "fecha_ranking",
        "fecha_actual",
        "ranking_global",
        "prioridad",
    }
    df = pd.read_csv(
        ranking_path,
        usecols=lambda column: column in summary_columns,
    )
    summary: dict[str, Any] = {
        "path": str(ranking_path),
        "exists": True,
        "rows": int(len(df)),
    }

    if "fecha_ranking" in df.columns and not df.empty:
        summary["fecha_ranking"] = str(df["fecha_ranking"].dropna().max())
    elif "fecha_actual" in df.columns and not df.empty:
        summary["fecha_ranking"] = str(df["fecha_actual"].dropna().max())

    if "ranking_global" in df.columns:
        summary["evaluadas"] = int(df["ranking_global"].notna().sum())
        summary["sin_ranking"] = int(df["ranking_global"].isna().sum())

    if "prioridad" in df.columns:
        summary["prioridades"] = df["prioridad"].value_counts(dropna=False).to_dict()

    return summary


def _database_url() -> str | None:
    load_dotenv()
    return os.getenv("DATABASE_URL")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _processing_health(
    state: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if state.get("status") != "processing":
        return state

    value = state.get("started_at_utc") or state.get("last_run_utc")
    if not value:
        return state
    try:
        started = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return state
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    elapsed_seconds = max(0, int((current - started).total_seconds()))
    try:
        stale_hours = float(
            os.getenv(
                "PIPELINE_PROCESSING_STALE_HOURS",
                str(DEFAULT_PROCESSING_STALE_HOURS),
            )
        )
    except ValueError:
        stale_hours = DEFAULT_PROCESSING_STALE_HOURS

    enriched = dict(state)
    enriched["processing_elapsed_seconds"] = elapsed_seconds
    enriched["processing_stale"] = elapsed_seconds >= stale_hours * 3600
    return enriched


def _ranking_coverage_from_postgis() -> dict[str, Any]:
    database_url = _database_url()
    if not database_url:
        return {"source": "csv", "available": False}

    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        fecha_ranking,
                        parcelas_rankeadas,
                        parcelas_objetivo,
                        cobertura_ratio,
                        elegible_latest
                    FROM ranking_hidrico_cobertura_fechas
                    ORDER BY fecha_ranking DESC
                    LIMIT 30
                    """
                )
                rows = [
                    {key: _jsonable(value) for key, value in dict(row).items()}
                    for row in cur.fetchall()
                ]

                cur.execute("SELECT fecha_ranking FROM ranking_hidrico_latest_date")
                latest_row = cur.fetchone()
                operational_date = (
                    _jsonable(latest_row["fecha_ranking"])
                    if latest_row and latest_row["fecha_ranking"]
                    else None
                )
    except Exception as exc:
        return {
            "source": "postgis",
            "available": False,
            "error": str(exc),
        }

    latest_detected = rows[0] if rows else None
    latest_detected_date = (
        latest_detected.get("fecha_ranking") if latest_detected else None
    )
    latest_detected_eligible = (
        bool(latest_detected.get("elegible_latest")) if latest_detected else False
    )
    status = "sin_rankings"
    if latest_detected:
        status = (
            "operativo_actualizado"
            if latest_detected_date == operational_date and latest_detected_eligible
            else "ultima_fecha_descartada_por_cobertura"
        )

    return {
        "source": "postgis",
        "available": True,
        "status": status,
        "operational_date": operational_date,
        "latest_detected_date": latest_detected_date,
        "latest_detected": latest_detected,
        "history": rows,
    }


def pipeline_state() -> dict[str, Any]:
    state = _safe_read_json(PIPELINE_STATE_PATH)
    if not state:
        return {
            "source": "state_file",
            "exists": False,
            "path": str(PIPELINE_STATE_PATH),
            "ranking_coverage": _ranking_coverage_from_postgis(),
        }

    state = _processing_health(state)
    ranking_latest = state.get("ranking_latest")
    if not ranking_latest and not state.get("skipped"):
        ranking_latest = "backend/data/rankings/ranking_hidrico_latest.csv"

    return {
        "source": "state_file",
        "exists": True,
        "path": str(PIPELINE_STATE_PATH),
        "state": state,
        "ranking_summary": _ranking_summary(ranking_latest),
        "ranking_coverage": _ranking_coverage_from_postgis(),
    }
