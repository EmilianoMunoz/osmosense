#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

ENABLE=false
START=false
CHOWN_SERVICE_USER=false

usage() {
    cat <<EOF
Uso:
  deployment/scripts/install_systemd.sh [--chown-service-user] [--enable] [--start]

Instala las units systemd de OSMOSENSE.

Por defecto:
  - copia units a /etc/systemd/system;
  - ejecuta systemctl daemon-reload;
  - no habilita ni arranca servicios.

Opciones:
  --chown-service-user  cambia propiedad de /opt/osmosense a osmosense:osmosense.
  --enable              habilita API, dashboard, pipeline timer y backup timer.
  --start               arranca API, dashboard, pipeline timer y backup timer.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --chown-service-user)
            CHOWN_SERVICE_USER=true
            ;;
        --enable)
            ENABLE=true
            ;;
        --start)
            START=true
            ENABLE=true
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

require_file() {
    if [[ ! -f "$1" ]]; then
        echo "Falta $1" >&2
        exit 1
    fi
}

require_sudo() {
    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo es requerido para instalar systemd units." >&2
        exit 1
    fi
}

install_units() {
    require_sudo
    local units=(
        osmosense-api.service
        osmosense-dashboard.service
        osmosense-pipeline.service
        osmosense-pipeline.timer
        osmosense-postgis-backup.service
        osmosense-postgis-backup.timer
    )

    for unit in "${units[@]}"; do
        require_file "deployment/systemd/$unit"
        log "Instalando $unit"
        sudo cp "deployment/systemd/$unit" /etc/systemd/system/
    done

    if [[ "$CHOWN_SERVICE_USER" == true ]]; then
        log "Cambiando propiedad de /opt/osmosense a osmosense:osmosense"
        sudo chown -R osmosense:osmosense /opt/osmosense
    fi

    sudo systemctl daemon-reload

    if [[ "$ENABLE" == true ]]; then
        log "Habilitando servicios"
        sudo systemctl enable osmosense-api.service
        sudo systemctl enable osmosense-dashboard.service
        sudo systemctl enable osmosense-pipeline.timer
        sudo systemctl enable osmosense-postgis-backup.timer
    fi

    if [[ "$START" == true ]]; then
        log "Arrancando servicios"
        sudo systemctl start osmosense-api.service
        sudo systemctl start osmosense-dashboard.service
        sudo systemctl start osmosense-pipeline.timer
        sudo systemctl start osmosense-postgis-backup.timer
    fi

    log "Instalación systemd finalizada"
}

install_units
