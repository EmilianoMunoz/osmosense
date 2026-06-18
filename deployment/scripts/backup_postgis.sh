#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${POSTGIS_BACKUP_DIR:-/opt/osmosense/backend/data/backups/postgis}"
POSTGIS_CONTAINER="${POSTGIS_CONTAINER_NAME:-estres-postgis}"
POSTGRES_DB_NAME="${POSTGRES_DB:-estres}"
POSTGRES_USER_NAME="${POSTGRES_USER:-estres}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT="$BACKUP_DIR/estres_${TIMESTAMP}.sql.gz"
TMP="${OUTPUT}.tmp"

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "DATABASE_URL no está configurado." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
trap 'rm -f "$TMP"' EXIT

dump_postgis() {
    if command -v docker >/dev/null 2>&1 \
        && docker inspect "$POSTGIS_CONTAINER" >/dev/null 2>&1; then
        docker exec "$POSTGIS_CONTAINER" \
            pg_dump -U "$POSTGRES_USER_NAME" -d "$POSTGRES_DB_NAME"
        return
    fi

    pg_dump "$DATABASE_URL"
}

dump_postgis | gzip -c > "$TMP"
gzip -t "$TMP"
mv "$TMP" "$OUTPUT"
trap - EXIT

echo "Backup PostGIS generado: $OUTPUT"
