#!/usr/bin/env bash
# Recompila el sitio si los datos del Mercado cambiaron desde el último build.
# Lo llama corillo-api tras cada cambio (con 20 s de espera para agrupar) y un cron cada 10 min
# (vendidos que cumplen 14 días, o un deploy de CI que dejó las páginas del Mercado sin datos).
# El build en sí es scripts/deploy-corillo.sh: respalda dist, compila, revierte si falla, con candado.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
API="${MERCADO_API:-http://127.0.0.1:3004/mercado/resumen}"
STATE="${MERCADO_REBUILD_STATE:-$HOME/.cache/corillo-mercado-build.md5}"
LOG="${MERCADO_REBUILD_LOG:-$HOME/.cache/corillo-mercado-build.log}"
mkdir -p "$(dirname "$STATE")"

actual="$(curl -fsS --max-time 10 "$API" | md5sum | cut -d' ' -f1)" || { echo "$(date -Is) API no responde; no se compila" >> "$LOG"; exit 0; }
# Si dist no tiene la página del Mercado (p. ej. tras un rsync de CI), se fuerza el build.
if [ -f "$STATE" ] && [ "$(cat "$STATE")" = "$actual" ] && [ -f "$REPO/dist/mercado/index.html" ]; then
  exit 0
fi
if bash "$REPO/scripts/deploy-corillo.sh" >> "$LOG" 2>&1; then
  echo "$actual" > "$STATE"
  echo "$(date -Is) build OK ($actual)" >> "$LOG"
else
  echo "$(date -Is) build FALLÓ (dist anterior restaurado por deploy-corillo.sh)" >> "$LOG"
fi
