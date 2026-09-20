#!/usr/bin/env bash
# Redeploy del bot Corillo Reel: rebuild de la imagen + re-lanzar el contenedor
# montando cookies.txt (Instagram exige sesión logueada).
set -euo pipefail

cd "$(dirname "$0")"

COOKIES="$PWD/cookies.txt"

if [[ ! -f "$COOKIES" ]]; then
  echo "❌ Falta $COOKIES"
  echo "   Exporta las cookies de Instagram (extensión 'Get cookies.txt LOCALLY',"
  echo "   formato Netscape) y súbelas ahí antes de redeployar."
  exit 1
fi

echo "🔨 Reconstruyendo imagen..."
docker build -t corillo-reel:latest .

echo "🧹 Removiendo contenedor anterior..."
docker rm -f corillo-reel 2>/dev/null || true

echo "🚀 Lanzando contenedor..."
docker run -d --name corillo-reel \
  --network marcossantiago-web_default \
  --env-file .env \
  -v "$COOKIES:/app/cookies.txt:ro" \
  --restart unless-stopped \
  corillo-reel:latest

echo "✅ Listo. Logs en vivo:  docker logs -f corillo-reel"
docker ps --filter name=corillo-reel --format 'table {{.Names}}\t{{.Status}}'
