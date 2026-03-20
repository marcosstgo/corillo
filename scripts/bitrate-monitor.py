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
AUTO_KICK_KBPS = 6500  # ⛔ kick automático
COOLDOWN             = 300   # segundos entre alertas por streamer
KICK_COOLDOWN        = 35    # segundos entre kicks — permite reconexión pero vuelve a kickear si bitrate sigue alto
KICK_NOTIFY_COOLDOWN = 300   # segundos entre notificaciones Telegram por kick (no spamear)
KICK_STRIKES_NEEDED  = 2     # polls consecutivos sobre AUTO_KICK_KBPS antes de kickear (~60s sostenido)
KICK_EXEMPT          = {"live/streamerpro", "live/katatonia", "live/marcos"}  # streamers exentos del auto-kick (alertas siguen activas)
KICK_DIR       = "/var/www/stream/assets/kick"

prev_bytes       = {}
last_alert       = {}
last_kick        = {}
last_kick_notify = {}
kick_strikes     = {}   # contador de polls consecutivos sobre AUTO_KICK_KBPS por streamer
was_over_limit   = set()

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

    print(f"KICK: {name} @ {kbps} Kbps — {'⛔ kickeado' if ok else '⚠️ fallo'}")

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

            # ⛔ Auto-kick — requiere KICK_STRIKES_NEEDED polls consecutivos sobre el límite
            if kbps >= AUTO_KICK_KBPS and name not in KICK_EXEMPT:
                was_over_limit.add(name)
                kick_strikes[name] = kick_strikes.get(name, 0) + 1
                strikes = kick_strikes[name]
                print(f"BITRATE ALTO: {name} @ {kbps} Kbps (strike {strikes}/{KICK_STRIKES_NEEDED})")

                if strikes == 1:
                    # Primer poll alto: aviso anticipado, aún no kickear
                    if now - last_alert.get(name, 0) > COOLDOWN:
                        last_alert[name] = now
                        send_telegram(
                            f"⚠️ <b>BITRATE ALTO</b>\n"
                            f"Streamer: <code>{name}</code>\n"
                            f"Bitrate: <b>{kbps:,} Kbps</b> (límite: {AUTO_KICK_KBPS:,} Kbps)\n"
                            f"Si continúa en el próximo poll (~30s), se kickeará automáticamente."
                        )

                elif strikes >= KICK_STRIKES_NEEDED:
                    # Bitrate sostenido — kickear
                    if now - last_kick.get(name, 0) > KICK_COOLDOWN:
                        last_kick[name] = now
                        last_alert[name] = now
                        ok = kick_publisher(p, kbps)
                        if now - last_kick_notify.get(name, 0) > KICK_NOTIFY_COOLDOWN:
                            last_kick_notify[name] = now
                            status = "⛔ kickeado" if ok else "⚠️ fallo el kick"
                            send_telegram(
                                f"⛔ <b>AUTO-KICK</b>\n"
                                f"Streamer: <code>{name}</code>\n"
                                f"Bitrate: <b>{kbps:,} Kbps</b> (límite: {AUTO_KICK_KBPS:,} Kbps)\n"
                                f"Estado: {status}"
                            )

            else:
                # Bitrate bajo el límite — resetear strikes
                kick_strikes.pop(name, None)

                # ✅ Recuperado — notificar si hubo kick reciente
                if name in was_over_limit:
                    was_over_limit.discard(name)
                    if last_kick.get(name, 0) > now - 600:
                        send_telegram(
                            f"✅ <b>BITRATE RECUPERADO</b>\n"
                            f"Streamer: <code>{name}</code>\n"
                            f"Bitrate actual: <b>{kbps:,} Kbps</b> — dentro del límite"
                        )
                        print(f"RECUPERADO: {name} @ {kbps} Kbps")

                # 🟡 Aviso moderado (5,000–5,999 Kbps)
                elif kbps >= WARN_KBPS:
                    if now - last_alert.get(name, 0) > COOLDOWN:
                        send_telegram(
                            f"🟡 <b>AVISO BITRATE</b>\n"
                            f"Streamer: <code>{name}</code>\n"
                            f"Bitrate: <b>{kbps:,} Kbps</b>\n"
                            f"Límite recomendado: 5,000 Kbps — considera bajar calidad"
                        )
                        last_alert[name] = now
                        print(f"AVISO: {name} @ {kbps} Kbps")

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
