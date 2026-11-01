#!/usr/bin/env python3
"""update-cine.py — cartelera de cine para corillo.live/cine/ desde TMDB (1-nov-2026).

Escribe src/data/cine.json con tres listas: «pegao» (tendencia de la semana), «cartelera» (en cines en Puerto Rico) y
«proximos» (próximos estrenos en PR). Por cada película: fecha de estreno EN PUERTO RICO (si TMDB no la tiene, la de EE. UU.),
duración, clasificación, géneros, dirección, reparto, tráiler oficial de YouTube y en qué app se ve en PR.
Las fichas propias (src/content/cine/*.md) ganan sobre esto (ver src/data/cine.ts).

Llave: TMDB_API_KEY (v3) o TMDB_TOKEN (lectura v4) en ~/.config/corillo/tokens.env.
Uso:  python3 scripts/update-cine.py [--publicar]   (--publicar = si cambió, commit + publicar_corillo.sh main)
Atribución obligatoria de TMDB: la pone /cine/ («Datos e imágenes de TMDB…»).
"""
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

REPO = Path(os.environ.get('CORILLO_REPO', Path.home() / 'Corillo/web'))
SALIDA = REPO / 'src/data/cine.json'
SERVER = Path.home() / 'Corillo/server/scripts/server'
IMG = 'https://image.tmdb.org/t/p'
LANG = 'es-MX'   # español latinoamericano (TMDB no tiene es-PR)


def cargar_env():
    f = Path.home() / '.config/corillo/tokens.env'
    if f.exists():
        for l in f.read_text().splitlines():
            if '=' in l and not l.lstrip().startswith('#'):
                k, v = l.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def cliente() -> httpx.Client:
    tok, key = os.environ.get('TMDB_TOKEN'), os.environ.get('TMDB_API_KEY')
    if not (tok or key):
        sys.exit('Falta TMDB_API_KEY o TMDB_TOKEN en ~/.config/corillo/tokens.env')
    return httpx.Client(base_url='https://api.themoviedb.org/3', timeout=20,
                        headers={'Authorization': f'Bearer {tok}'} if tok else {},
                        params={} if tok else {'api_key': key})


def lista(c, ruta, paginas=2, **params):
    out = []
    for pag in range(1, paginas + 1):
        r = c.get(ruta, params={'language': LANG, 'page': pag, **params})
        r.raise_for_status()
        out += r.json().get('results', [])
    return out


def fecha_pr(rd: dict) -> tuple[str | None, str | None]:
    """(fecha AAAA-MM-DD, clasificación) del estreno en cines en PR; si no hay, EE. UU."""
    por = {x['iso_3166_1']: x['release_dates'] for x in rd.get('results', [])}
    for pais in ('PR', 'US'):
        cines = [d for d in por.get(pais, []) if d.get('type') in (2, 3)] or por.get(pais, [])
        if cines:
            d = min(cines, key=lambda d: d['release_date'])
            cert = next((x.get('certification') for x in por.get(pais, []) if x.get('certification')), None)
            return d['release_date'][:10], cert
    return None, None


def trailer(videos: list) -> tuple[str | None, str | None]:
    yt = [v for v in videos if v.get('site') == 'YouTube' and v.get('type') == 'Trailer']
    yt.sort(key=lambda v: (not v.get('official'), v.get('iso_639_1') != 'es', v.get('published_at', '')))
    return (yt[0]['key'], None) if yt else (None, None)


def detalle(c, mid: int, popularidad: float) -> dict | None:
    r = c.get(f'/movie/{mid}', params={'language': LANG,
                                       'append_to_response': 'release_dates,credits,videos,watch/providers',
                                       'include_video_language': 'es,en'})
    if r.status_code != 200:
        return None
    d = r.json()
    titulo = d.get('title') or d.get('original_title') or ''
    if titulo and not all(ord(ch) < 0x0250 or not ch.isalpha() for ch in titulo):
        # sin título en español y el original no es de alfabeto latino (hindi, japonés…): el de EE. UU.
        en = c.get(f'/movie/{mid}', params={'language': 'en-US'})
        if en.status_code == 200 and en.json().get('title'):
            d['title'] = en.json()['title']
    estreno, cert = fecha_pr(d.get('release_dates', {}))
    tr, _ = trailer(d.get('videos', {}).get('results', []))
    prov = d.get('watch/providers', {}).get('results', {})
    pr_prov = prov.get('PR') or prov.get('US') or {}
    donde = [{'name': p['provider_name']} for p in pr_prov.get('flatrate', [])[:5]]
    paises = {x['iso_3166_1'] for x in d.get('production_countries', [])}
    return {
        'tmdb': mid, 'title': d.get('title') or d.get('original_title'), 'original': d.get('original_title'),
        'estreno': estreno or d.get('release_date') or None, 'clasificacion': cert, 'duracion': d.get('runtime') or None,
        'resumen': (d.get('overview') or '').strip(), 'generos': [g['name'] for g in d.get('genres', [])],
        'afiche': f"{IMG}/w342{d['poster_path']}" if d.get('poster_path') else None,
        'fondo': f"{IMG}/w1280{d['backdrop_path']}" if d.get('backdrop_path') else None,
        'direccion': [p['name'] for p in d.get('credits', {}).get('crew', []) if p.get('job') == 'Director'][:3],
        'reparto': [p['name'] for p in d.get('credits', {}).get('cast', [])[:8]],
        'trailer': tr, 'dondeVer': donde, 'popularidad': round(popularidad or d.get('popularity') or 0, 1),
        'pr': 'PR' in paises,
    }


def main():
    cargar_env()
    c = cliente()
    hoy = date.today()
    crudo = {
        'pegao': lista(c, '/trending/movie/week', paginas=1),
        'cartelera': lista(c, '/movie/now_playing', region='PR') or lista(c, '/movie/now_playing', region='US'),
        'proximos': [m for m in lista(c, '/movie/upcoming', paginas=3, region='US')
                     if m.get('release_date', '') >= hoy.isoformat()],
    }
    cache: dict[int, dict] = {}
    out = {'actualizado': time.strftime('%Y-%m-%dT%H:%M:%S'), 'pegao': [], 'cartelera': [], 'proximos': []}
    for k, pelis in crudo.items():
        for m in pelis[:30]:
            if m.get('adult') or not m.get('poster_path'):
                continue
            if m['id'] not in cache:
                d = detalle(c, m['id'], m.get('popularity', 0))
                if not d:
                    continue
                cache[m['id']] = d
            d = cache[m['id']]
            if k == 'proximos' and not (d['estreno'] and hoy.isoformat() < d['estreno'] <= (hoy + timedelta(days=120)).isoformat()):
                continue
            out[k].append(d)
    viejo = json.loads(SALIDA.read_text()) if SALIDA.exists() else {}
    cambio = {k: v for k, v in out.items() if k != 'actualizado'} != {k: v for k, v in viejo.items() if k != 'actualizado'}
    print(f"pegao {len(out['pegao'])} · cartelera {len(out['cartelera'])} · próximos {len(out['proximos'])} · "
          f"{'CAMBIÓ' if cambio else 'sin cambios'}")
    if not cambio:
        return
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    if '--publicar' in sys.argv:
        subprocess.run(['git', '-C', str(REPO), 'add', str(SALIDA)], check=True)
        subprocess.run(['git', '-C', str(REPO), 'commit', '-qm', 'Cine: cartelera de TMDB al día'], check=True)
        subprocess.run(['bash', str(SERVER / 'publicar_corillo.sh'), 'main'], check=True, timeout=1800)


if __name__ == '__main__':
    main()
