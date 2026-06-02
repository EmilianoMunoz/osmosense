from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.rankings import (
    admin_assign_cliente_parcela,
    admin_activar_parcela_disponible,
    admin_cliente_parcelas,
    admin_clientes,
    admin_create_cliente,
    admin_create_parcela,
    admin_deactivate_parcela,
    admin_delete_cliente_parcela,
    admin_parcela,
    admin_parcelas,
    admin_parcelas_disponibles,
    admin_update_cliente,
    admin_update_parcela,
    clientes,
    latest_geojson,
    latest_geojson_cliente,
    latest_ranking,
    ranking_by_fecha,
    regional_um_latest,
    regional_um_latest_geojson,
    regional_um_parcelas_latest_geojson,
)


class ClienteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cliente_id: int | None = Field(default=None, ge=1)
    nombre: str = Field(min_length=1)
    tipo: str = Field(pattern="^(particular|regional)$")
    descripcion: str | None = None
    activo: bool = True


class ClienteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1)
    tipo: str | None = Field(default=None, pattern="^(particular|regional)$")
    descripcion: str | None = None
    activo: bool | None = None


class ClienteParcelaAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parcela_id: int = Field(ge=1)
    etiqueta: str | None = None


class ParcelaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parcela_id: int = Field(ge=1)
    cultivo_oficial: str = Field(pattern="^(vid|olivo)$")
    geometry: dict
    area_m2: float | None = Field(default=None, gt=0)
    fuente: str = "manual"
    globalid: str | None = None
    cultivo_original: str | None = None
    activo: bool = True


class ParcelaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cultivo_oficial: str | None = Field(default=None, pattern="^(vid|olivo)$")
    geometry: dict | None = None
    area_m2: float | None = Field(default=None, gt=0)
    fuente: str | None = None
    globalid: str | None = None
    cultivo_original: str | None = None
    activo: bool | None = None


class ParcelaDisponibleActivar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cultivo_oficial: str = Field(pattern="^(vid|olivo)$")
    cliente_id: int | None = Field(default=None, ge=1)
    etiqueta: str | None = None


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


@app.get("/admin/parcelas")
def get_admin_parcelas(
    limit: int | None = Query(default=None, ge=1, le=5000),
    cultivo: str | None = Query(default=None, pattern="^(vid|olivo)$"),
    activo: bool | None = Query(default=True),
) -> dict:
    try:
        return admin_parcelas(limit=limit, cultivo=cultivo, activo=activo)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/parcelas/disponibles")
def get_admin_parcelas_disponibles(
    limit: int | None = Query(default=None, ge=1, le=5000),
) -> dict:
    try:
        return admin_parcelas_disponibles(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/parcelas/{parcela_id}/activar-disponible")
def post_admin_activar_parcela_disponible(
    parcela_id: int,
    payload: ParcelaDisponibleActivar,
) -> dict:
    try:
        return admin_activar_parcela_disponible(
            parcela_id=parcela_id,
            cultivo_oficial=payload.cultivo_oficial,
            cliente_id=payload.cliente_id,
            etiqueta=payload.etiqueta,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/parcelas/{parcela_id}")
def get_admin_parcela(parcela_id: int) -> dict:
    try:
        return admin_parcela(parcela_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/parcelas", status_code=201)
def post_admin_parcela(payload: ParcelaCreate) -> dict:
    try:
        return admin_create_parcela(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/admin/parcelas/{parcela_id}")
def put_admin_parcela(parcela_id: int, payload: ParcelaUpdate) -> dict:
    try:
        return admin_update_parcela(
            parcela_id,
            payload.model_dump(exclude_unset=True),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/admin/parcelas/{parcela_id}")
def delete_admin_parcela(parcela_id: int) -> dict:
    try:
        return admin_deactivate_parcela(parcela_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/clientes")
def get_admin_clientes(limit: int | None = Query(default=None, ge=1, le=5000)) -> dict:
    try:
        return admin_clientes(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/clientes", status_code=201)
def post_admin_cliente(payload: ClienteCreate) -> dict:
    try:
        return admin_create_cliente(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/admin/clientes/{cliente_id}")
def put_admin_cliente(cliente_id: int, payload: ClienteUpdate) -> dict:
    try:
        return admin_update_cliente(
            cliente_id,
            payload.model_dump(exclude_unset=True),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/clientes/{cliente_id}/parcelas")
def get_admin_cliente_parcelas(cliente_id: int) -> dict:
    try:
        return admin_cliente_parcelas(cliente_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/clientes/{cliente_id}/parcelas", status_code=201)
def post_admin_cliente_parcela(cliente_id: int, payload: ClienteParcelaAssign) -> dict:
    try:
        return admin_assign_cliente_parcela(
            cliente_id,
            payload.parcela_id,
            payload.etiqueta,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/admin/clientes/{cliente_id}/parcelas/{parcela_id}")
def delete_admin_cliente_parcela(cliente_id: int, parcela_id: int) -> dict:
    try:
        return admin_delete_cliente_parcela(cliente_id, parcela_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
