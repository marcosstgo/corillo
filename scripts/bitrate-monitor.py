#!/usr/bin/env python3
"""
Bitrate monitor for corillo.live
Polls MediaMTX every INTERVAL seconds, sends Telegram alerts,
and auto-kicks publishers that exceed AUTO_KICK_KBPS.

Env vars (set in /home/marcos/bitrate-monitor.env):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""
import os, time, json, subprocess, requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT  = os.environ["TELEGRAM_CHAT_ID"]
MEDIAMTX_API   = "http://localhost:9997"
INTERVAL       = 30    # segundos entre polls
WARN_KBPS      = 5000  # 🟡 aviso
ALERT_KBPS     = 8000  # 🔴 alerta alta
AUTO_KICK_KBPS = 6000  # ⛔ kick automático
COOLDOWN       = 300   # segundos entre alertas por streamer
KICK_COOLDOWN  = 120   # segundos entre kicks por streamer (evita loop en reconexión)
KICK_DIR       = "/var/www/stream/assets/kick"

prev_bytes  = {}
last_alert  = {}
last_kick   = {}

os.makedirs(KICK_DIR, exist_ok=True)


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
    """Kickea al publisher cortando el socket TCP via ss -K y notifica por Telegram."""
    name = path_item["name"]

    # Obtener remoteAddr desde /v3/rtmpconns/list (la API de kick no existe en v1.16.1)
    ok = False
    try:
        r = requests.get(f"{MEDIAMTX_API}/v3/rtmpconns/list", timeout=5)
        conns = r.json().get("items", [])
        conn = next((c for c in conns if c.get("path") == name and c.get("state") == "publish"), None)
        if conn:
            remote = conn["remoteAddr"]          # "ip:port"
            ip, port = remote.rsplit(":", 1)
            result = subprocess.run(
                ["sudo", "ss", "-K", f"dst {ip}", f"dport = {port}"],
                capture_output=True, text=True, timeout=5
            )
            ok = result.returncode == 0
            print(f"KICK ss -K dst {ip} dport {port}: rc={result.returncode}")
        else:
            print(f"KICK SKIP: {name} — no encontrado en rtmpconns/list")
    except Exception as e:
        print(f"KICK ERROR: {name} — {e}")

    status = "⛔ kickeado" if ok else "⚠️ fallo el kick"
    send_telegram(
        f"⛔ <b>AUTO-KICK</b>\n"
        f"Streamer: <code>{name}</code>\n"
        f"Bitrate: <b>{kbps:,} Kbps</b> (límite: {AUTO_KICK_KBPS:,} Kbps)\n"
        f"Estado: {status}"
    )
    print(f"KICK: {name} @ {kbps} Kbps — {status}")

    # Escribir flag para que el player muestre mensaje de kick al streamer
    if ok:
        channel_key = name.removeprefix("live/")
        try:
            with open(f"{KICK_DIR}/{channel_key}.json", "w") as f:
                json.dump({"ts": time.time(), "kbps": kbps}, f)
        except Exception as e:
            print(f"KICK FLAG ERROR: {e}")

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
