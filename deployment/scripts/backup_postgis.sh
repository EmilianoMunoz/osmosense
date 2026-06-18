#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${POSTGIS_BACKUP_DIR:-/opt/osmosense/backend/data/backups/postgis}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT="$BACKUP_DIR/estres_${TIMESTAMP}.sql.gz"
TMP="${OUTPUT}.tmp"

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "DATABASE_URL no está configurado." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
trap 'rm -f "$TMP"' EXIT

pg_dump "$DATABASE_URL" | gzip -c > "$TMP"
gzip -t "$TMP"
mv "$TMP" "$OUTPUT"
trap - EXIT

echo "Backup PostGIS generado: $OUTPUT"
