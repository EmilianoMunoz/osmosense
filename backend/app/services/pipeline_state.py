from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PIPELINE_STATE_PATH = Path("backend/data/state/pipeline_hidrico_state.json")


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

    df = pd.read_csv(ranking_path)
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


def pipeline_state() -> dict[str, Any]:
    state = _safe_read_json(PIPELINE_STATE_PATH)
    if not state:
        return {
            "source": "state_file",
            "exists": False,
            "path": str(PIPELINE_STATE_PATH),
        }

    ranking_latest = state.get("ranking_latest")
    if not ranking_latest and not state.get("skipped"):
        ranking_latest = "backend/data/rankings/ranking_hidrico_latest.csv"

    return {
        "source": "state_file",
        "exists": True,
        "path": str(PIPELINE_STATE_PATH),
        "state": state,
        "ranking_summary": _ranking_summary(ranking_latest),
    }
