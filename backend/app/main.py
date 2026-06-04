from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.auth import authenticate_user, verify_access_token
from backend.app.services.rankings import (
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
from backend.app.services.pipeline_state import pipeline_state
from backend.app.services.users import admin_create_usuario, admin_update_usuario, admin_usuarios


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


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UsuarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1)
    nombre: str | None = None
    rol: str = Field(pattern="^(admin|regional|productor)$")
    cliente_id: int | None = Field(default=None, ge=1)
    password: str = Field(min_length=6)
    activo: bool = True


class UsuarioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, min_length=1)
    nombre: str | None = None
    rol: str | None = Field(default=None, pattern="^(admin|regional|productor)$")
    cliente_id: int | None = Field(default=None, ge=1)
    password: str | None = Field(default=None, min_length=6)
    activo: bool | None = None


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token requerido.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_roles(*roles: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["rol"] not in roles:
            raise HTTPException(status_code=403, detail="Rol no autorizado.")
        return user

    return dependency


def require_cliente_or_admin(
    cliente_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user["rol"] == "admin":
        return user
    if user["rol"] == "productor" and user.get("cliente_id") == cliente_id:
        return user
    raise HTTPException(status_code=403, detail="Productor no autorizado.")


app = FastAPI(
    title="API Estrés Hídrico San Rafael",
    version="0.1.0",
    description="API para ranking hídrico de parcelas de vid y olivo.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/login")
def post_auth_login(payload: LoginRequest) -> dict:
    try:
        return authenticate_user(payload.email, payload.password)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/rankings/latest")
def get_latest_ranking(
    limit: int | None = Query(default=None, ge=1, le=5000),
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return latest_ranking(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/rankings/latest/geojson")
def get_latest_ranking_geojson(
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return latest_geojson()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/pipeline/state")
def get_pipeline_state(
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return pipeline_state()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/clientes")
def get_clientes(_user: dict[str, Any] = Depends(require_roles("admin"))) -> dict:
    try:
        return clientes()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/parcelas")
def get_admin_parcelas(
    limit: int | None = Query(default=None, ge=1, le=5000),
    cultivo: str | None = Query(default=None, pattern="^(vid|olivo)$"),
    activo: bool | None = Query(default=True),
    _user: dict[str, Any] = Depends(require_roles("admin")),
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
    _user: dict[str, Any] = Depends(require_roles("admin")),
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
    _user: dict[str, Any] = Depends(require_roles("admin")),
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
def get_admin_parcela(
    parcela_id: int,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_parcela(parcela_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/parcelas", status_code=201)
def post_admin_parcela(
    payload: ParcelaCreate,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_create_parcela(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/admin/parcelas/{parcela_id}")
def put_admin_parcela(
    parcela_id: int,
    payload: ParcelaUpdate,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
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
def delete_admin_parcela(
    parcela_id: int,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_deactivate_parcela(parcela_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/clientes")
def get_admin_clientes(
    limit: int | None = Query(default=None, ge=1, le=5000),
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_clientes(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/usuarios")
def get_admin_usuarios(
    limit: int | None = Query(default=None, ge=1, le=5000),
    activo: bool | None = Query(default=None),
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_usuarios(limit=limit, activo=activo)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/usuarios", status_code=201)
def post_admin_usuario(
    payload: UsuarioCreate,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_create_usuario(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/admin/usuarios/{usuario_id}")
def put_admin_usuario(
    usuario_id: int,
    payload: UsuarioUpdate,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_update_usuario(
            usuario_id,
            payload.model_dump(exclude_unset=True),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/clientes", status_code=201)
def post_admin_cliente(
    payload: ClienteCreate,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_create_cliente(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/admin/clientes/{cliente_id}")
def put_admin_cliente(
    cliente_id: int,
    payload: ClienteUpdate,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
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
def get_admin_cliente_parcelas(
    cliente_id: int,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_cliente_parcelas(cliente_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/admin/clientes/{cliente_id}/parcelas", status_code=201)
def post_admin_cliente_parcela(
    cliente_id: int,
    payload: ClienteParcelaAssign,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
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
def delete_admin_cliente_parcela(
    cliente_id: int,
    parcela_id: int,
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return admin_delete_cliente_parcela(cliente_id, parcela_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/clientes/{cliente_id}/rankings/latest/geojson")
def get_latest_ranking_geojson_cliente(
    cliente_id: int,
    _user: dict[str, Any] = Depends(require_cliente_or_admin),
) -> dict:
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
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return ranking_by_fecha(fecha=fecha, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/regional/um/latest")
def get_regional_um_latest(
    limit: int | None = Query(default=None, ge=1, le=5000),
    _user: dict[str, Any] = Depends(require_roles("admin", "regional")),
) -> dict:
    try:
        return regional_um_latest(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/regional/um/latest/geojson")
def get_regional_um_latest_geojson(
    _user: dict[str, Any] = Depends(require_roles("admin", "regional")),
) -> dict:
    try:
        return regional_um_latest_geojson()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/regional/um/{um_id}/parcelas/latest/geojson")
def get_regional_um_parcelas_latest_geojson(
    um_id: int,
    _user: dict[str, Any] = Depends(require_roles("admin", "regional")),
) -> dict:
    try:
        return regional_um_parcelas_latest_geojson(um_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
