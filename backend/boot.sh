#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
cd "$ROOT_DIR"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
STREAMLIT_HOST="${STREAMLIT_HOST:-127.0.0.1}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
LOG_DIR="${LOG_DIR:-backend/data/logs/boot}"
PID_DIR="${PID_DIR:-backend/data/state}"
API_PID_FILE="$PID_DIR/api.pid"
STREAMLIT_PID_FILE="$PID_DIR/streamlit.pid"
POSTGIS_COMPOSE="docker-compose.postgis.yml"
DEFAULT_DATABASE_URL="postgresql://estres:estres_dev@127.0.0.1:5433/estres"

ACTION="${1:-start}"
shift || true

RUN_SETUP=false
ALL_PARCELAS=false
RUN_SMOKE=false
RUN_UPDATE_RANKING=false
API_ONLY=false
DASHBOARD_ONLY=false

usage() {
    cat <<EOF
Uso:
  ./boot.sh start [--setup] [--all-parcelas] [--update-ranking] [--smoke] [--api-only|--dashboard-only]
  ./boot.sh stop
  ./boot.sh restart [--setup] [--all-parcelas] [--update-ranking] [--smoke]
  ./boot.sh status

Variables opcionales:
  API_HOST=127.0.0.1 API_PORT=8000 STREAMLIT_PORT=8501 ./boot.sh start

Notas:
  --setup         aplica schema y carga datos operativos en PostGIS.
  --all-parcelas con --setup carga todas las parcelas oficiales para disponibles.
  --update-ranking consulta Sentinel/GEE y recalcula/carga ranking solo si hay fecha nueva.
  --smoke         corre smoke test API/PostGIS al final.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --setup)
            RUN_SETUP=true
            ;;
        --all-parcelas)
            ALL_PARCELAS=true
            ;;
        --smoke)
            RUN_SMOKE=true
            ;;
        --update-ranking)
            RUN_UPDATE_RANKING=true
            ;;
        --api-only)
            API_ONLY=true
            ;;
        --dashboard-only)
            DASHBOARD_ONLY=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Argumento desconocido: $1" >&2
            usage
            exit 2
            ;;
    esac
    shift
done

mkdir -p "$LOG_DIR" "$PID_DIR"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_file() {
    if [[ ! -f "$1" ]]; then
        echo "Falta $1" >&2
        exit 1
    fi
}

ensure_env() {
    if [[ ! -f ".env" ]]; then
        log "No existe .env; copiando .env.postgis.example"
        cp .env.postgis.example .env
    fi
}

ensure_venv() {
    if [[ ! -x "venv/bin/python" ]]; then
        echo "No existe venv/bin/python. Crear venv e instalar requirements antes de boot." >&2
        exit 1
    fi
}

is_pid_running() {
    local pid_file="$1"
    [[ -f "$pid_file" ]] || return 1
    local pid
    pid="$(cat "$pid_file")"
    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" >/dev/null 2>&1
}

stop_pid() {
    local name="$1"
    local pid_file="$2"
    if is_pid_running "$pid_file"; then
        local pid
        pid="$(cat "$pid_file")"
        log "Deteniendo $name pid=$pid"
        kill "$pid" >/dev/null 2>&1 || true
        for _ in {1..20}; do
            if ! kill -0 "$pid" >/dev/null 2>&1; then
                break
            fi
            sleep 0.25
        done
        if kill -0 "$pid" >/dev/null 2>&1; then
            log "$name no terminó; enviando SIGKILL"
            kill -9 "$pid" >/dev/null 2>&1 || true
        fi
    fi
    rm -f "$pid_file"
}

start_postgis() {
    require_file "$POSTGIS_COMPOSE"
    log "Levantando PostGIS"
    docker compose -f "$POSTGIS_COMPOSE" up -d
    log "Esperando healthcheck de PostGIS"
    for _ in {1..60}; do
        local status
        status="$(docker inspect -f '{{.State.Health.Status}}' estres-postgis 2>/dev/null || true)"
        if [[ "$status" == "healthy" ]]; then
            log "PostGIS healthy"
            return
        fi
        sleep 1
    done
    echo "PostGIS no llegó a estado healthy." >&2
    docker compose -f "$POSTGIS_COMPOSE" ps
    exit 1
}

setup_postgis() {
    local args=(venv/bin/python backend/scripts/postgis/setup_postgis_local.py)
    if [[ "$ALL_PARCELAS" == true ]]; then
        args+=(--all-parcelas)
    fi
    log "Aplicando setup PostGIS: ${args[*]}"
    "${args[@]}"
}

start_api() {
    if is_pid_running "$API_PID_FILE"; then
        log "API ya está corriendo pid=$(cat "$API_PID_FILE")"
        return
    fi
    log "Levantando API http://${API_HOST}:${API_PORT}"
    DATABASE_URL="${DATABASE_URL:-$DEFAULT_DATABASE_URL}" \
        nohup venv/bin/uvicorn backend.app.main:app --host "$API_HOST" --port "$API_PORT" \
        > "$LOG_DIR/api.log" 2>&1 &
    echo $! > "$API_PID_FILE"
}

start_dashboard() {
    if is_pid_running "$STREAMLIT_PID_FILE"; then
        log "Streamlit ya está corriendo pid=$(cat "$STREAMLIT_PID_FILE")"
        return
    fi
    log "Levantando Streamlit http://${STREAMLIT_HOST}:${STREAMLIT_PORT}"
    API_BASE_URL="${API_BASE_URL:-http://${API_HOST}:${API_PORT}}" \
        nohup venv/bin/streamlit run streamlit_app.py \
        --server.address "$STREAMLIT_HOST" \
        --server.port "$STREAMLIT_PORT" \
        > "$LOG_DIR/streamlit.log" 2>&1 &
    echo $! > "$STREAMLIT_PID_FILE"
}

wait_api() {
    log "Esperando API"
    for _ in {1..40}; do
        if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
            log "API disponible"
            return
        fi
        sleep 0.5
    done
    echo "API no respondió. Ver $LOG_DIR/api.log" >&2
    exit 1
}

run_smoke() {
    log "Ejecutando smoke test"
    API_BASE_URL="http://${API_HOST}:${API_PORT}" \
        DATABASE_URL="${DATABASE_URL:-$DEFAULT_DATABASE_URL}" \
        venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
}

run_update_ranking() {
    log "Ejecutando pipeline hídrico con búsqueda de nueva imagen Sentinel"
    DATABASE_URL="${DATABASE_URL:-$DEFAULT_DATABASE_URL}" \
        venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py \
        --mode cloud \
        --update-sentinel \
        --parcel-source postgis \
        --skip-if-no-new-date \
        --load-postgis
}

status() {
    if docker info >/dev/null 2>&1; then
        docker compose -f "$POSTGIS_COMPOSE" ps || true
    else
        log "Docker no disponible para este usuario/sesión"
    fi
    if is_pid_running "$API_PID_FILE"; then
        log "API corriendo pid=$(cat "$API_PID_FILE") http://${API_HOST}:${API_PORT}"
    else
        log "API detenida"
    fi
    if is_pid_running "$STREAMLIT_PID_FILE"; then
        log "Streamlit corriendo pid=$(cat "$STREAMLIT_PID_FILE") http://${STREAMLIT_HOST}:${STREAMLIT_PORT}"
    else
        log "Streamlit detenido"
    fi
}

start() {
    ensure_venv
    ensure_env
    if [[ "$DASHBOARD_ONLY" != true ]]; then
        start_postgis
        if [[ "$RUN_SETUP" == true ]]; then
            setup_postgis
        fi
        if [[ "$RUN_UPDATE_RANKING" == true ]]; then
            run_update_ranking
        fi
        start_api
        wait_api
    fi
    if [[ "$API_ONLY" != true ]]; then
        start_dashboard
    fi
    if [[ "$RUN_SMOKE" == true ]]; then
        run_smoke
    fi
    log "Listo"
    status
}

stop() {
    stop_pid "Streamlit" "$STREAMLIT_PID_FILE"
    stop_pid "API" "$API_PID_FILE"
    log "Servicios app detenidos. PostGIS queda levantado; detenerlo con:"
    log "docker compose -f $POSTGIS_COMPOSE down"
}

case "$ACTION" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        start
        ;;
    status)
        status
        ;;
    *)
        echo "Acción desconocida: $ACTION" >&2
        usage
        exit 2
        ;;
esac
