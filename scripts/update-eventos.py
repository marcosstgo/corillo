#!/usr/bin/env python3
"""update-eventos.py — eventos de videojuegos en Puerto Rico para corillo.live/eventos/ y El Bochinchero (1-nov-2026).

Fuente automática: el calendario público del Salón de la Fama del Gaming en Puerto Rico (se usan solo los hechos: nombre, fecha
y lugar; siempre con crédito y enlace). Fuente a mano: src/data/eventos-propios.json, verificada con el organizador, que gana.

Lo que solo sale del calendario queda confirmado=false: se enseña en la página con esa advertencia, pero el bot no lo dice y Google no
lo recibe como Event. Se saltan cartas y ligas de tienda (TCG, VGC, Pokémon): Marcos quiere eventos de videojuegos.
No usar fuentes que bloqueen programas (Discover Puerto Rico, Ticketera) ni copiar texto de Yo Soy Un Gamer sin su permiso escrito.

Uso:  python3 scripts/update-eventos.py [--publicar]   (--publicar = si cambió, commit + publicar_corillo.sh main)
"""
import html
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

REPO = Path(os.environ.get('CORILLO_REPO', Path.home() / 'Corillo/web'))
SALIDA = REPO / 'src/data/eventos.json'
PROPIOS = REPO / 'src/data/eventos-propios.json'
SERVER = Path.home() / 'Corillo/server/scripts/server'
FUENTE_NOMBRE = 'Salón de la Fama del Gaming en Puerto Rico'
FUENTE_URL = 'https://salonfamagamingpr.org/calendario-de-eventos-de-videojuegos-y-esports-en-puerto-rico/'
API = 'https://salonfamagamingpr.org/wp-json/wp/v2/pages'
AGENTE = 'Mozilla/5.0 (compatible; CorilloBot/1.0; +https://corillo.live)'
ZONA = ZoneInfo('America/Puerto_Rico')
MESES = {m: i + 1 for i, m in enumerate(['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
                                         'octubre', 'noviembre', 'diciembre'])}
MINIMO_FILAS = 10            # menos que esto: la página cambió; mejor fallar y avisar que borrar los eventos

_VIDEOJUEGOS = re.compile(r'videojuego|e-?sports?\b|\bgaming\b|\bgamer|\barcade\b|\bfgc\b|fighting game|lan party|street fighter|tekken|'
                          r'smash bros|mortal kombat|guilty gear|2xko|call of duty|warzone|fortnite|valorant|rocket league|apex legends|'
                          r'battlefield|league of legends|counter-?strike|overwatch|rainbow six|\bpubg\b|\bea sports\b|\bfc ?2\d\b|nba ?2k|\bebaseball\b|mlb the show', re.I)
_NO = re.compile(r'\bTCG\b|\bVGC\b|League (Challenge|Cup)|Pre-?Release|Pok[eé]mon|Yu-?Gi-?Oh|Magic: |Lorcana|One Piece Card|'
                 r'\bcasino|\bapuesta', re.I)


_REPETIDOS = re.compile(r'#\s*\d+|weekly|community events|qualifier', re.I)


def _texto(fragmento: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'(?s)<[^>]+>', ' ', fragmento))).strip()


def slug_de(nombre: str) -> str:
    t = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')[:70]


def filas(contenido: str) -> list[dict]:
    """Calendario → filas. Formato: <h2>🗓️ Noviembre 2026</h2> y <li><strong>14–15 de noviembre</strong> — <em>Nombre</em> | lugar | …</li>."""
    salida, anio = [], None
    for m in re.finditer(r'(?is)<h2\b[^>]*>(.*?)</h2>|<li\b[^>]*>\s*<strong>(.*?)</strong>\s*[—–-]?\s*<em>(.*?)</em>(.*?)</li>', contenido):
        if m.group(1) is not None:
            h = re.search(r'(' + '|'.join(MESES) + r') (\d{4})', _texto(m.group(1)), re.I)
            anio = int(h.group(2)) if h else None
            continue
        f = re.fullmatch(r'(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))? de (\w+)', _texto(m.group(2)), re.I)
        if not f or anio is None or f.group(3).lower() not in MESES:
            continue
        mes = MESES[f.group(3).lower()]
        try:
            ini, fin = date(anio, mes, int(f.group(1))), date(anio, mes, int(f.group(2) or f.group(1)))
        except ValueError:
            continue
        if fin < ini:
            continue
        partes = [x.strip() for x in _texto(m.group(4)).split('|') if x.strip()]
        salida.append({'nombre': _texto(m.group(3)), 'inicio': ini.isoformat(), 'fin': fin.isoformat(),
                       'lugar_completo': partes[0] if partes else '', 'detalle': ' · '.join(partes[1:])})
    return salida


def es_de_videojuegos(f: dict) -> bool:
    texto = f"{f['nombre']} {f['detalle']}"
    return not _NO.search(texto) and bool(_VIDEOJUEGOS.search(texto))


def separar_lugar(completo: str) -> tuple[str, str]:
    partes = [p.strip() for p in re.sub(r',?\s*PR$', '', completo).rsplit(',', 1)]
    return (partes[0], partes[1]) if len(partes) == 2 else (partes[0], '')


def combinar(calendario: list[dict], propios: list[dict], hoy: date) -> list[dict]:
    """Solo lo que no ha terminado. Lo propio gana: se reconoce por el mismo nombre."""
    por_slug = {}
    for f in calendario:
        if not es_de_videojuegos(f) or f['fin'] < hoy.isoformat():
            continue
        lugar, municipio = separar_lugar(f['lugar_completo'])
        por_slug[slug_de(f['nombre'])] = {
            'nombre': f['nombre'], 'inicio': f['inicio'], 'fin': f['fin'], 'lugar': lugar, 'municipio': municipio,
            'detalle': f['detalle'], 'precio': '', 'web': '', 'confirmado': False, 'fuente_nombre': FUENTE_NOMBRE,
            'fuente_url': FUENTE_URL, 'voz_extra': ''}
    for p in propios:
        if p['fin'] < hoy.isoformat():
            por_slug.pop(slug_de(p['nombre']), None)
            continue
        por_slug[slug_de(p['nombre'])] = {'precio': '', 'web': '', 'voz_extra': '', 'detalle': '', **p}
    return [{'slug': s, **e} for s, e in sorted(por_slug.items(), key=lambda x: (x[1]['inicio'], x[0]))]


def recientes(calendario: list[dict], hoy: date, tope: int = 8) -> list[dict]:
    """Torneos que ya pasaron, para enseñar que hay escena. Sin semanales ni actividades sueltas: se repetirían."""
    salida, vistos = [], set()
    for f in sorted(calendario, key=lambda x: x['inicio'], reverse=True):
        slug = slug_de(f['nombre'])
        if f['fin'] >= hoy.isoformat() or slug in vistos or not es_de_videojuegos(f) or _REPETIDOS.search(f['nombre']):
            continue
        vistos.add(slug)
        lugar, municipio = separar_lugar(f['lugar_completo'])
        salida.append({'nombre': f['nombre'], 'inicio': f['inicio'], 'fin': f['fin'], 'lugar': lugar, 'municipio': municipio, 'detalle': f['detalle']})
        if len(salida) == tope:
            break
    return salida


def bajar_calendario() -> str:
    r = httpx.get(API, params={'slug': FUENTE_URL.rstrip('/').rsplit('/', 1)[1]}, headers={'User-Agent': AGENTE}, timeout=30,
                  follow_redirects=True)
    r.raise_for_status()
    return r.json()[0]['content']['rendered']


def main():
    hoy = datetime.now(ZONA).date()
    cal = filas(bajar_calendario())
    if len(cal) < MINIMO_FILAS:
        sys.exit(f'El calendario dio solo {len(cal)} filas: ¿cambió la página? No toco los eventos.')
    propios = [e for e in json.loads(PROPIOS.read_text())['eventos']]
    eventos = combinar(cal, propios, hoy)
    viejo = json.loads(SALIDA.read_text()) if SALIDA.exists() else {}
    pasados = recientes(cal, hoy)
    cambio = eventos != viejo.get('eventos') or pasados != viejo.get('pasados')
    print(f"calendario {len(cal)} filas · {len(eventos)} próximos ({sum(e['confirmado'] for e in eventos)} confirmados) · "
          f"{'CAMBIÓ' if cambio else 'sin cambios'}")
    for e in eventos:
        print(f"  {'✓' if e['confirmado'] else '?'} {e['inicio']} {e['nombre']} — {e['lugar']}, {e['municipio']}")
    if not cambio:
        return
    SALIDA.write_text(json.dumps({'actualizado': hoy.isoformat(), 'eventos': eventos, 'pasados': pasados}, ensure_ascii=False, indent=1) + '\n')
    if '--publicar' in sys.argv:
        subprocess.run(['git', '-C', str(REPO), 'add', str(SALIDA)], check=True)
        subprocess.run(['git', '-C', str(REPO), 'commit', '-qm', 'Eventos: calendario al día'], check=True)
        subprocess.run(['bash', str(SERVER / 'publicar_corillo.sh'), 'main'], check=True, timeout=1800)


if __name__ == '__main__':
    main()
