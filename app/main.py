from fastapi import FastAPI, HTTPException, Query

from app.services.rankings import (
    clientes,
    latest_geojson,
    latest_geojson_cliente,
    latest_ranking,
    ranking_by_fecha,
    regional_um_latest,
    regional_um_latest_geojson,
    regional_um_parcelas_latest_geojson,
)


app = FastAPI(
    title="API Estrés Hídrico San Rafael",
    version="0.1.0",
    description="API para ranking hídrico de parcelas de vid y olivo.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/rankings/latest")
def get_latest_ranking(limit: int | None = Query(default=None, ge=1, le=5000)) -> dict:
    try:
        return latest_ranking(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/rankings/latest/geojson")
def get_latest_ranking_geojson() -> dict:
    try:
        return latest_geojson()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/clientes")
def get_clientes() -> dict:
    try:
        return clientes()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/clientes/{cliente_id}/rankings/latest/geojson")
def get_latest_ranking_geojson_cliente(cliente_id: int) -> dict:
    try:
        return latest_geojson_cliente(cliente_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/rankings/{fecha}")
def get_ranking_by_fecha(
    fecha: str,
    limit: int | None = Query(default=None, ge=1, le=5000),
) -> dict:
    try:
        return ranking_by_fecha(fecha=fecha, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/regional/um/latest")
def get_regional_um_latest(limit: int | None = Query(default=None, ge=1, le=5000)) -> dict:
    try:
        return regional_um_latest(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/regional/um/latest/geojson")
def get_regional_um_latest_geojson() -> dict:
    try:
        return regional_um_latest_geojson()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/regional/um/{um_id}/parcelas/latest/geojson")
def get_regional_um_parcelas_latest_geojson(um_id: int) -> dict:
    try:
        return regional_um_parcelas_latest_geojson(um_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
