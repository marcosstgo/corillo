#!/usr/bin/env python3
"""Fila de publicaciones del Corillo para el grupo de WhatsApp (vía OpenClaw, vinculado al WhatsApp de Marcos).

Las noticias (daily-news.py), las ofertas y juegos gratis (update-deals.py) y los avisos de "en vivo"
(corillo-telegram) dejan sus mensajes aquí con enqueue(). El repartidor (este archivo, cron cada 10 min)
los manda de a uno y repartidos en el día, para que el grupo no reciba todo de golpe.

Reglas: solo de 9 a. m. a 9 p. m. (hora de PR), mínimo GAP_MIN minutos entre mensajes, tope diario total
y por tipo, y gana la prioridad (en vivo > noticia > juego gratis > oferta). Lo vencido se descarta.
Apagado si WHATSAPP_GROUP no está en ~/corillo-wa/.env.
"""
import datetime as dt, fcntl, json, os, subprocess, sys
from pathlib import Path

HOME = Path('/home/corillo-adm/corillo-wa'); HOME.mkdir(parents=True, exist_ok=True)
QUEUE = HOME / 'queue.json'; LOCK = HOME / '.lock'; ENV = HOME / '.env'
TZ = dt.timezone(dt.timedelta(hours=-4))
HOURS = (9, 21)
GAP_MIN = 75
DAILY_MAX = 6
KINDS = {  # tipo -> (prioridad, máximo al día, horas de vida por defecto)
    'envivo': (40, 2, 1), 'noticia': (30, 1, 14), 'gratis': (20, 1, 48), 'oferta': (10, 3, 24),
}


def _now(): return dt.datetime.now(TZ)


def _load():
    try: return json.loads(QUEUE.read_text())
    except Exception: return {'pending': [], 'sent': []}


def _save(q):
    tmp = QUEUE.with_suffix('.tmp'); tmp.write_text(json.dumps(q, ensure_ascii=False)); tmp.replace(QUEUE)


def enqueue(kind, key, text, media=None, hours=None, score=0):
    """Deja un mensaje en la fila. `key` evita duplicados (la misma oferta o noticia no entra dos veces)."""
    if kind not in KINDS: raise ValueError(kind)
    with open(LOCK, 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        q = _load()
        if any(x['key'] == key for x in q['pending'] + q['sent']): return False
        exp = _now() + dt.timedelta(hours=hours or KINDS[kind][2])
        q['pending'].append({'kind': kind, 'key': key, 'text': text, 'media': media, 'score': score,
                             'created': _now().isoformat(timespec='seconds'), 'expires': exp.isoformat(timespec='seconds')})
        _save(q)
    return True


def _group():
    if not ENV.exists(): return None
    for l in ENV.read_text().splitlines():
        if l.startswith('WHATSAPP_GROUP='): return l.split('=', 1)[1].strip() or None


def _wa_up():
    st = subprocess.run(['/usr/bin/openclaw', 'channels', 'status'], capture_output=True, text=True, timeout=60).stdout
    line = next((l for l in st.splitlines() if 'WhatsApp' in l), '')
    return 'stopped' not in line and 'disconnected' not in line


def _revive(stamp):
    """Si el canal de WhatsApp quedó parado (p. ej. tras un corte de DNS, 8-oct), reinicia el gateway; máx 1 vez/hora."""
    mark = HOME / '.last_restart'
    if mark.exists() and mark.stat().st_mtime > _now().timestamp() - 3600: return
    mark.touch()
    r = subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'openclaw'], capture_output=True, text=True, timeout=60)
    print(stamp, 'canal de WhatsApp parado; reinicio del gateway:', 'OK' if r.returncode == 0 else r.stderr.strip()[-200:])


def dispatch(dry=False):
    now = _now()
    with open(LOCK, 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        q = _load()
        q['pending'] = [x for x in q['pending'] if dt.datetime.fromisoformat(x['expires']) > now]      # lo vencido no se manda
        cut = (now - dt.timedelta(days=30)).isoformat()
        q['sent'] = [x for x in q['sent'] if x['at'] > cut]
        for f in (HOME / 'cards').glob('*.png'):                          # tarjetas de noticias viejas
            if f.stat().st_mtime < now.timestamp() - 30 * 86400: f.unlink(missing_ok=True)
        _save(q)
        group = _group()
        if not group: print('apagado (falta WHATSAPP_GROUP)'); return
        if not HOURS[0] <= now.hour < HOURS[1]: return
        today = [x for x in q['sent'] if x['at'][:10] == now.date().isoformat()]
        if len(today) >= DAILY_MAX: return
        since = now - dt.datetime.fromisoformat(max(x['at'] for x in q['sent'])) if q['sent'] else dt.timedelta(days=1)
        def gap(k): return dt.timedelta(minutes=30 if k == 'envivo' else GAP_MIN)   # un "en vivo" no puede esperar mucho
        ok = [x for x in q['pending'] if since >= gap(x['kind']) and sum(1 for t in today if t['kind'] == x['kind']) < KINDS[x['kind']][1]]
        if not ok: return
        it = max(ok, key=lambda x: (KINDS[x['kind']][0], x.get('score', 0), x['created']))
        cmd = ['/usr/bin/openclaw', 'message', 'send', '--channel', 'whatsapp', '--target', group, '--message', it['text'], '--json']
        if it.get('media'): cmd += ['--media', it['media']]
        if dry: cmd.append('--dry-run')
        stamp = now.strftime('%Y-%m-%d %H:%M')
        # Con el canal caído no se manda: OpenClaw guarda el intento y lo reenvía al reconectar,
        # y como aquí también se reintenta, el grupo recibía el mismo mensaje repetido (8-oct).
        if not dry and not _wa_up():
            print(stamp, 'WhatsApp desconectado; no se envía (se reintenta en 10 min)'); _revive(stamp); return
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(stamp, 'WhatsApp falló (se reintenta en 10 min):', (r.stdout + r.stderr)[-200:].replace('\n', ' ')); return
        print(stamp, 'enviado' if not dry else 'prueba OK', it['kind'], it['key'])
        if not dry:
            q['pending'].remove(it)
            q['sent'].append({'kind': it['kind'], 'key': it['key'], 'at': now.isoformat(timespec='seconds')})
            _save(q)


if __name__ == '__main__':
    if '--ver' in sys.argv:
        q = _load(); print(json.dumps({'pendientes': [(x['kind'], x['key'], x['expires'][11:16]) for x in q['pending']],
                                       'enviados_hoy': [(x['kind'], x['key'], x['at'][11:16]) for x in q['sent'] if x['at'][:10] == _now().date().isoformat()]},
                                      ensure_ascii=False, indent=1))
    else:
        dispatch(dry='--dry-run' in sys.argv)
