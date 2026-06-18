#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

INSTALL_DOCKER=false
SKIP_PACKAGES=false

usage() {
    cat <<EOF
Uso:
  deployment/scripts/bootstrap_vm.sh [--install-docker] [--skip-packages]

Prepara una VM Ubuntu para OSMOSENSE:
  - instala paquetes base;
  - opcionalmente instala Docker y docker compose plugin;
  - crea/actualiza venv;
  - instala requirements.txt;
  - crea .env desde .env.cloud.example si falta;
  - crea usuario de servicio osmosense si falta.

No carga datos, no rota credenciales y no instala systemd.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-docker)
            INSTALL_DOCKER=true
            ;;
        --skip-packages)
            SKIP_PACKAGES=true
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

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_sudo() {
    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo es requerido para instalar paquetes/usuario de servicio." >&2
        exit 1
    fi
}

install_packages() {
    require_sudo
    log "Instalando paquetes base"
    sudo apt update
    sudo apt install -y \
        build-essential \
        curl \
        git \
        postgresql-client \
        python3-dev \
        python3-venv

    if [[ "$INSTALL_DOCKER" == true ]]; then
        log "Instalando Docker"
        sudo apt install -y docker.io docker-compose-plugin
        sudo usermod -aG docker "$USER"
        log "Docker instalado. Cerrar y abrir sesión para aplicar grupo docker si era necesario."
    fi
}

ensure_service_user() {
    require_sudo
    if id osmosense >/dev/null 2>&1; then
        log "Usuario de servicio osmosense ya existe"
        return
    fi
    log "Creando usuario de servicio osmosense"
    sudo useradd --system --home /opt/osmosense --shell /usr/sbin/nologin osmosense
}

ensure_venv() {
    if [[ ! -d venv ]]; then
        log "Creando venv"
        python3 -m venv venv
    fi
    log "Actualizando pip"
    venv/bin/python -m pip install --upgrade pip
    log "Instalando requirements"
    venv/bin/pip install -r requirements.txt
}

ensure_env() {
    if [[ -f .env ]]; then
        log ".env ya existe; no se sobrescribe"
    else
        log "Creando .env desde .env.cloud.example"
        cp .env.cloud.example .env
    fi
    chmod 600 .env
    log "Revisar .env antes de continuar: DATABASE_URL, AUTH_SECRET, GEE_PROJECT_ID y API_BASE_URL."
}

main() {
    if [[ "$SKIP_PACKAGES" != true ]]; then
        install_packages
    fi
    ensure_service_user
    ensure_venv
    ensure_env
    mkdir -p backend/data/backups/postgis backend/data/logs backend/data/state
    log "Bootstrap finalizado"
    log "Siguiente paso: editar .env y ejecutar run_preflight_cloud.py."
}

main
