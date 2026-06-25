#!/usr/bin/env bash
# Deploy seguro de corillo: respalda dist, build, y hace rollback si el build falla.
# Uso: bash scripts/deploy-corillo.sh
set -euo pipefail
cd "$(dirname "$0")/.."

TS=$(date +%Y%m%d_%H%M%S)
BAK="dist.bak-$TS"

if [ -d dist ]; then
  echo "→ Respaldando dist actual en $BAK"
  cp -a dist "$BAK"
fi

echo "→ Building (npm run build)…"
if npm run build; then
  echo "✓ Build OK. Sitio desplegado. Respaldo: $BAK"
  # conservar solo los últimos 3 respaldos
  ls -dt dist.bak-* 2>/dev/null | tail -n +4 | xargs -r rm -rf
else
  echo "✗ BUILD FALLÓ — restaurando dist anterior…"
  rm -rf dist
  [ -d "$BAK" ] && mv "$BAK" dist && echo "✓ Rollback completo (dist restaurado)."
  exit 1
fi
