#!/bin/bash
# audit.sh — compara repo vs producción para todos los archivos críticos
# Uso: bash scripts/audit.sh

PASS=0
FAIL=0

check() {
  local label=$1 repo=$2 prod=$3
  if [ ! -f "$prod" ]; then
    echo "  MISSING  $label ($prod no existe)"
    ((FAIL++))
  elif diff -q "$repo" "$prod" > /dev/null 2>&1; then
    echo "  OK       $label"
    ((PASS++))
  else
    echo "  DIFF     $label"
    diff "$repo" "$prod"
    ((FAIL++))
  fi
}

echo ""
echo "=== CORILLO AUDIT $(date '+%Y-%m-%d %H:%M') ==="
echo ""

check "nginx.conf"          /var/www/stream/nginx.conf                    /etc/nginx/nginx.conf
check "mediamtx.yml"        /var/www/stream/mediamtx.yml                  /etc/mediamtx/mediamtx.yml
check "api/server.py"       /var/www/stream/api/server.py                 /home/corillo-adm/corillo-api/server.py
check "auth/server.py"      /var/www/stream/auth/server.py                /home/corillo-adm/corillo-auth/server.py
check "chat/server.py"      /var/www/stream/chat/server.py                /home/corillo-adm/corillo-bot/server.py
check "chat/system_prompt"  /var/www/stream/chat/system_prompt.py         /home/corillo-adm/corillo-bot/system_prompt.py
check "telegram/server.py"  /var/www/stream/telegram/server.py            /home/corillo-adm/corillo-telegram/server.py
check "vod-process.py"      /var/www/stream/scripts/vod-process.py        /home/corillo-adm/corillo-vod/vod-process.py

echo ""
echo "Servicios:"
for svc in nginx corillo-api corillo-auth corillo-bot corillo-telegram corillo-thumbs mediamtx pocketbase; do
  status=$(systemctl is-active $svc 2>/dev/null)
  if [ "$status" = "active" ]; then
    echo "  OK       $svc"
  else
    echo "  DOWN     $svc ($status)"
    ((FAIL++))
  fi
done

echo ""
if [ $FAIL -eq 0 ]; then
  echo "Todo OK — $PASS checks pasaron"
else
  echo "$FAIL problema(s) encontrado(s), $PASS OK"
fi
echo ""
