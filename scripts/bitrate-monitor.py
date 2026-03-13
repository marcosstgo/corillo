#!/usr/bin/env python3
"""
Bitrate monitor for corillo.live
Polls MediaMTX every INTERVAL seconds, sends Telegram alerts,
and auto-kicks publishers that exceed AUTO_KICK_KBPS.

Env vars (set in /home/marcos/bitrate-monitor.env):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""
import os, time, requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT  = os.environ["TELEGRAM_CHAT_ID"]
MEDIAMTX_API   = "http://localhost:9997"
INTERVAL       = 30    # segundos entre polls
WARN_KBPS      = 5000  # 🟡 aviso
ALERT_KBPS     = 8000  # 🔴 alerta alta
AUTO_KICK_KBPS = 6000  # ⛔ kick automático
COOLDOWN       = 300   # segundos entre alertas por streamer
KICK_COOLDOWN  = 120   # segundos entre kicks por streamer (evita loop en reconexión)

prev_bytes  = {}
last_alert  = {}
last_kick   = {}


def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"Telegram error: {e}")


def kick_publisher(path_item, kbps):
    """Kickea al publisher via MediaMTX API y notifica por Telegram."""
    name   = path_item["name"]
    source = path_item.get("source", {})
    src_id = source.get("id")
    src_type = source.get("type", "")

    # Mapeo tipo → endpoint de kick
    endpoint_map = {
        "rtmpConn":  f"{MEDIAMTX_API}/v3/rtmpconns/{src_id}/kick",
        "rtmpsConn": f"{MEDIAMTX_API}/v3/rtmpsconns/{src_id}/kick",
        "srtConn":   f"{MEDIAMTX_API}/v3/srtconns/{src_id}/kick",
    }
    url = endpoint_map.get(src_type)
    if not url or not src_id:
        print(f"KICK SKIP: {name} — tipo desconocido o sin ID ({src_type})")
        return False

    try:
        r = requests.post(url, timeout=5)
        ok = r.status_code == 200
    except Exception as e:
        print(f"KICK ERROR: {name} — {e}")
        ok = False

    status = "⛔ kickeado" if ok else "⚠️ fallo el kick"
    send_telegram(
        f"⛔ <b>AUTO-KICK</b>\n"
        f"Streamer: <code>{name}</code>\n"
        f"Bitrate: <b>{kbps:,} Kbps</b> (límite: {AUTO_KICK_KBPS:,} Kbps)\n"
        f"Estado: {status}"
    )
    print(f"KICK: {name} @ {kbps} Kbps — {status}")
    return ok


def check():
    try:
        r = requests.get(f"{MEDIAMTX_API}/v3/paths/list", timeout=5)
        paths = r.json().get("items", [])
    except Exception as e:
        print(f"API error: {e}")
        return

    now = time.time()
    for p in paths:
        if not p.get("ready"):
            continue
        name = p["name"]
        rx = p.get("bytesReceived", 0)

        if name in prev_bytes:
            delta_bytes = rx - prev_bytes[name]
            kbps = int(delta_bytes * 8 / 1000 / INTERVAL)

            # ⛔ Auto-kick por exceder límite
            if kbps >= AUTO_KICK_KBPS:
                if now - last_kick.get(name, 0) > KICK_COOLDOWN:
                    last_kick[name] = now
                    last_alert[name] = now  # resetea alerta también
                    kick_publisher(p, kbps)

            # 🔴 Alerta alta (entre ALERT y KICK, o si el kick falló)
            elif kbps >= ALERT_KBPS:
                if now - last_alert.get(name, 0) > COOLDOWN:
                    send_telegram(
                        f"🔴 <b>ALERTA 4K</b>\n"
                        f"Streamer: <code>{name}</code>\n"
                        f"Bitrate: <b>{kbps:,} Kbps</b>\n"
                        f"Límite recomendado: 5,000 Kbps\n"
                        f"Resolución estimada: 4K — avisa al streamer"
                    )
                    last_alert[name] = now
                    print(f"ALERTA 4K: {name} @ {kbps} Kbps")

            # 🟡 Aviso moderado
            elif kbps >= WARN_KBPS:
                if now - last_alert.get(name, 0) > COOLDOWN:
                    send_telegram(
                        f"🟡 <b>AVISO 2K</b>\n"
                        f"Streamer: <code>{name}</code>\n"
                        f"Bitrate: <b>{kbps:,} Kbps</b>\n"
                        f"Límite recomendado: 5,000 Kbps\n"
                        f"Resolución estimada: 2K — considera bajar calidad"
                    )
                    last_alert[name] = now
                    print(f"AVISO 2K: {name} @ {kbps} Kbps")

        prev_bytes[name] = rx

    # limpiar paths que ya no están en vivo
    active = {p["name"] for p in paths if p.get("ready")}
    for name in list(prev_bytes.keys()):
        if name not in active:
            del prev_bytes[name]


print("Bitrate monitor iniciado")
while True:
    check()
    time.sleep(INTERVAL)
