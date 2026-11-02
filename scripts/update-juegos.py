#!/usr/bin/env python3
"""update-juegos.py — lo más jugado en Steam para corillo.live/juegos/ (2-nov-2026).

Fuente: la API oficial de Steam (ISteamChartsService), sin llave. NO usar SteamDB: su FAQ prohíbe el scraping y ellos mismos
mandan a la API de Steam. Del catálogo de la tienda se guardan solo hechos (nombre, géneros, desarrollador, fecha), no sus textos.

Escribe:
  src/data/juegos.json           la foto de hoy (top 100)
  src/data/juegos-catalogo.json  todo juego que ha estado en el top; su página no desaparece si baja (Google ya la conoce)
  data/historial-juegos/AAAA-MM.jsonl  una línea por corrida. Steam no da historial: si no se guarda hoy, se pierde.

Uso:  python3 scripts/update-juegos.py [--publicar]   (--publicar = commit + publicar_corillo.sh main)
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

REPO = Path(os.environ.get('CORILLO_REPO', Path.home() / 'Corillo/web'))
FOTO = REPO / 'src/data/juegos.json'
CATALOGO = REPO / 'src/data/juegos-catalogo.json'
HISTORIAL = REPO / 'data/historial-juegos'
SERVER = Path.home() / 'Corillo/server/scripts/server'
AHORA_URL = 'https://api.steampowered.com/ISteamChartsService/GetGamesByConcurrentPlayers/v1/'
SEMANA_URL = 'https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/'
TIENDA_URL = 'https://store.steampowered.com/api/appdetails'
MINIMO = 50             # si Steam devuelve menos, algo anda mal: no se toca la página
PAUSA_TIENDA = 1.6      # la tienda limita (unas 200 consultas cada 5 min)
ZONA = ZoneInfo('America/Puerto_Rico')


def slug_de(nombre: str) -> str:
    t = unicodedata.normalize('NFKD', nombre.lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')


def limpiar_nombre(nombre: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[®™©]', '', nombre)).strip()


def ficha_de_tienda(http: httpx.Client, appid: int) -> dict | None:
    """Los hechos de la tienda, en español. None si Steam no la da (se reintenta en la próxima corrida)."""
    for intento in range(3):
        r = http.get(TIENDA_URL, params={'appids': appid, 'l': 'spanish', 'cc': 'us',
                                         'filters': 'basic,genres,developers,release_date'})
        if r.status_code == 429:
            time.sleep(60 * (intento + 1))
            continue
        r.raise_for_status()
        d = (r.json() or {}).get(str(appid)) or {}
        if not d.get('success') or not (d.get('data') or {}).get('name'):
            return None
        x = d['data']
        return {
            'nombre': limpiar_nombre(x['name']), 'tipo': x.get('type', 'game'), 'gratis': bool(x.get('is_free')),
            'generos': [g['description'] for g in x.get('genres') or []][:4],
            'desarrollador': ', '.join((x.get('developers') or [])[:2]),
            'lanzamiento': (x.get('release_date') or {}).get('date', ''),
            'imagen': x.get('header_image', ''),
        }
    return None


def asignar_slug(ficha: dict, appid: int, catalogo: dict) -> str:
    slug = slug_de(ficha['nombre']) or str(appid)
    usados = {c['slug'] for a, c in catalogo.items() if a != str(appid)}
    return f'{slug}-{appid}' if slug in usados else slug


def combinar(ahora: list[dict], semana: list[dict], catalogo: dict) -> list[dict]:
    """El top de ahora, solo con juegos de los que tenemos nombre; `cambio` = puestos ganados en el ranking semanal de Steam."""
    por_app = {g['appid']: g for g in semana}
    filas = []
    for g in ahora:
        if str(g['appid']) not in catalogo:
            continue
        s = por_app.get(g['appid'])
        cambio = None
        if s:
            cambio = 'nuevo' if not s.get('last_week_rank') else s['last_week_rank'] - s['rank']
        filas.append({'appid': g['appid'], 'puesto': g['rank'], 'ahora': g['concurrent_in_game'], 'pico': g['peak_in_game'],
                      'cambio': cambio})
    return filas


def main():
    http = httpx.Client(timeout=30, headers={'User-Agent': 'corillo.live (+https://corillo.live/juegos/)'}, follow_redirects=True)
    ahora_r = http.get(AHORA_URL); ahora_r.raise_for_status()
    ahora = ahora_r.json()['response']['ranks']
    semana_r = http.get(SEMANA_URL); semana_r.raise_for_status()
    semana = semana_r.json()['response']['ranks']
    if len(ahora) < MINIMO:
        sys.exit(f'FALLÓ: Steam devolvió {len(ahora)} juegos (mínimo {MINIMO}); no toqué nada')

    catalogo = json.loads(CATALOGO.read_text()) if CATALOGO.exists() else {}
    hoy = datetime.now(ZONA)
    faltan = 0
    for g in ahora:
        clave = str(g['appid'])
        if clave in catalogo:
            continue
        ficha = ficha_de_tienda(http, g['appid'])
        time.sleep(PAUSA_TIENDA)
        if not ficha:
            faltan += 1
            continue
        ficha['slug'] = asignar_slug(ficha, g['appid'], catalogo)
        ficha['visto_desde'] = hoy.strftime('%Y-%m-%d')
        catalogo[clave] = ficha
    if len(catalogo) < MINIMO:
        sys.exit(f'FALLÓ: solo tengo {len(catalogo)} juegos con nombre; no toqué nada')

    filas = combinar(ahora, semana, catalogo)
    for f in filas:                                    # lo último que se supo: para la página del que salga del top
        catalogo[str(f['appid'])]['ultimo'] = {'fecha': hoy.strftime('%Y-%m-%d'), 'puesto': f['puesto'], 'ahora': f['ahora'], 'pico': f['pico']}

    FOTO.write_text(json.dumps({'actualizado': hoy.isoformat(timespec='minutes'), 'juegos': filas}, ensure_ascii=False, indent=1) + '\n')
    CATALOGO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1, sort_keys=True) + '\n')
    HISTORIAL.mkdir(parents=True, exist_ok=True)
    with open(HISTORIAL / f'{hoy:%Y-%m}.jsonl', 'a') as h:
        h.write(json.dumps({'f': hoy.isoformat(timespec='minutes'), 'r': [[g['appid'], g['rank'], g['concurrent_in_game'], g['peak_in_game']] for g in ahora]}, separators=(',', ':')) + '\n')
    print(f'{len(filas)} juegos en la foto · {len(catalogo)} en el catálogo · {faltan} sin datos de la tienda')

    if '--publicar' in sys.argv:
        subprocess.run(['git', '-C', str(REPO), 'add', str(FOTO), str(CATALOGO), str(HISTORIAL)], check=True)
        subprocess.run(['git', '-C', str(REPO), 'commit', '-qm', 'Juegos: lo más jugado en Steam al día'], check=True)
        subprocess.run(['bash', str(SERVER / 'publicar_corillo.sh'), 'main'], check=True, timeout=1800)


if __name__ == '__main__':
    main()
