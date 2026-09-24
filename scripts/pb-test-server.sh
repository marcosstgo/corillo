#!/usr/bin/env bash
# Levanta una PocketBase DESECHABLE para pruebas (CI y local). No toca la de producción.
# Uso: scripts/pb-test-server.sh [puerto]   → imprime la URL y deja el proceso en segundo plano.
set -euo pipefail
PB_VERSION=0.36.7
PORT="${1:-8099}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${PB_TEST_DIR:-$(mktemp -d)}"
BIN="${PB_BIN:-$WORK/pocketbase}"

if [ ! -x "$BIN" ]; then
  curl -fsSL -o "$WORK/pb.zip" \
    "https://github.com/pocketbase/pocketbase/releases/download/v${PB_VERSION}/pocketbase_${PB_VERSION}_linux_amd64.zip"
  unzip -oq "$WORK/pb.zip" pocketbase -d "$WORK"
  BIN="$WORK/pocketbase"
fi

mkdir -p "$WORK/migrations" "$WORK/data"
cp "$ROOT"/pb/test-fixtures/*.js "$WORK/migrations/"
cp "$ROOT"/pb/migrations/*.js "$WORK/migrations/" 2>/dev/null || true
[ -d "$ROOT/pb/hooks" ] && cp -r "$ROOT/pb/hooks" "$WORK/hooks" || mkdir -p "$WORK/hooks"

"$BIN" superuser upsert test@corillo.test testpass123456 \
  --dir "$WORK/data" --migrationsDir "$WORK/migrations" >/dev/null
nohup "$BIN" serve --http "127.0.0.1:$PORT" --dir "$WORK/data" \
  --migrationsDir "$WORK/migrations" --hooksDir "$WORK/hooks" > "$WORK/pb.log" 2>&1 &
echo $! > "$WORK/pb.pid"
for _ in $(seq 1 50); do
  curl -fs "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 0.2
done
curl -fs "http://127.0.0.1:$PORT/api/health" >/dev/null || { cat "$WORK/pb.log"; exit 1; }
echo "PB_TEST_URL=http://127.0.0.1:$PORT PB_TEST_DIR=$WORK"
