#!/home/corillo-adm/corillo-news/venv/bin/python
"""update-bf6.py — datos de corillo.live/bf6/ (10-nov-2026).

1. Anuncios oficiales: los del juego en Steam (ISteamNews/GetNewsForApp, sin llave, solo el canal
`steam_community_announcements`). De cada anuncio se guarda un título y un resumen corto EN ESPAÑOL, escritos en palabras
propias por Claude, más el enlace al anuncio original. No se copia el texto de EA.

Cada anuncio se resume una sola vez (se guarda por `gid`): una corrida sin anuncios nuevos no gasta nada.

2. Noticias de la prensa: titulares en español de Google News (búsqueda "Battlefield 6"), con su medio y enlace. Solo el
   titular, nunca el texto del artículo.
3. Canales: los últimos directos y videos de YouTube de los creadores de CANALES (sin llave: se lee la página pública del canal,
   porque YouTube ya no da el RSS; si cambia el formato, el canal queda como estaba y se avisa en el log).

Escribe:  src/data/bf6.json   { actualizado, noticias: [...], prensa: [...], canales: [...] }
Uso:      scripts/update-bf6.py [--sin-ia]   (--sin-ia = no llama a Claude; los nuevos salen con su título original)
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(os.environ.get('CORILLO_REPO', Path(__file__).resolve().parent.parent))
DATOS = REPO / 'src/data/bf6.json'
APPID = 2807960
NEWS_URL = 'https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/'
CLAN_IMG = 'https://clan.akamai.steamstatic.com/images'
GUARDAR = 12            # cuántos anuncios se quedan en la página
MODELO = os.environ.get('BF6_MODEL', 'claude-opus-5-5')
GNEWS_URL = 'https://news.google.com/rss/search'
PRENSA_DIAS = 21        # titulares más viejos que esto no salen
PRENSA_MAX = 12
PRENSA_HORAS = 6       # la prensa se vuelve a escoger como mucho cada 6 h (el sitio se publica varias veces al día)
NAVEGADOR = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36',
             'Accept-Language': 'es-419,es;q=0.9'}
# Creadores de BF6 que salen en la página. Marcos decide quién entra (10-nov-2026: CaptMatojo07, boricua).
CANALES = [
    {'handle': 'CaptMatojo07', 'nombre': 'Capitán Matojo', 'id': 'UCkMIq70Im_rSUo8KXMVDlXQ', 'pr': True},
]

SISTEMA = """Eres redactor de CORILLO (corillo.live), una comunidad de streaming y gaming de Puerto Rico.
Te dan un anuncio oficial de Battlefield 6 publicado en Steam (en inglés). Escribe en español neutro, claro y natural:
- "titulo": un título corto (máximo 80 caracteres) que diga qué trae el anuncio. Los nombres propios del juego
  (modos, mapas, armas, temporadas, REDSEC, Portal) se quedan como están.
- "resumen": 1 o 2 oraciones (máximo 260 caracteres) con lo más útil para un jugador: qué cambia, qué llega y cuándo.
Reglas: usa solo lo que dice el anuncio, no inventes fechas ni detalles; no copies frases enteras, dilo con tus palabras;
sin emojis, sin signos de exclamación y sin tono de anuncio publicitario."""

ESQUEMA = {
    'type': 'object',
    'properties': {'titulo': {'type': 'string'}, 'resumen': {'type': 'string'}},
    'required': ['titulo', 'resumen'],
    'additionalProperties': False,
}


def log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def cargar_llaves() -> None:
    f = Path.home() / '.config/corillo/tokens.env'
    if not f.exists():
        return
    for linea in f.read_text().splitlines():
        m = re.match(r'\s*(?:export\s+)?([A-Z0-9_]+)=(.*)$', linea)
        if m and m.group(1) not in os.environ:
            os.environ[m.group(1)] = m.group(2).strip().strip('"\'')


def texto_plano(bbcode: str) -> str:
    t = re.sub(r'\[img[^\]]*\].*?\[/img\]', ' ', bbcode, flags=re.S)
    t = re.sub(r'\[/?[a-z0-9*]+(?:[= ][^\]]*)?\]', ' ', t, flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def primera_imagen(bbcode: str) -> str | None:
    m = re.search(r'\{STEAM_CLAN_IMAGE\}(/[^"\]\s]+\.(?:jpg|jpeg|png|gif|webp))', bbcode, flags=re.I)
    if m:
        return CLAN_IMG + m.group(1)
    m = re.search(r'(https://[^"\]\s]+\.(?:jpg|jpeg|png|webp))', bbcode, flags=re.I)
    return m.group(1) if m else None


def anuncios() -> list[dict]:
    r = httpx.get(NEWS_URL, params={'appid': APPID, 'count': 30, 'maxlength': 0}, timeout=20)
    r.raise_for_status()
    items = r.json()['appnews']['newsitems']
    return [n for n in items if n.get('feedname') == 'steam_community_announcements'][:GUARDAR]


def prensa() -> list[dict]:
    import email.utils
    import html as H
    r = httpx.get(GNEWS_URL, params={'q': '"Battlefield 6" when:%dd' % PRENSA_DIAS, 'hl': 'es-419', 'gl': 'US', 'ceid': 'US:es-419'},
                  headers=NAVEGADOR, timeout=20, follow_redirects=True)
    r.raise_for_status()
    vistos, out = [], []
    for it in re.findall(r'<item>(.*?)</item>', r.text, re.S):
        g = lambda tag: (re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', it, re.S) or [None, ''])[1]
        titulo, medio = H.unescape(g('title')).strip(), H.unescape(g('source')).strip()
        if medio and titulo.endswith(' - ' + medio):
            titulo = titulo[: -len(medio) - 3].strip()
        if 'battlefield' not in titulo.lower():
            continue
        palabras = {w for w in re.findall(r'\w{4,}', titulo.lower()) if w not in ('battlefield', 'para', 'como', 'tras', 'ahora')}
        if any(len(palabras & v) / max(1, len(palabras | v)) > 0.3 for v in vistos):
            continue                    # la misma noticia en otro medio
        vistos.append(palabras)
        fecha = email.utils.parsedate_to_datetime(g('pubDate')).astimezone(timezone.utc)
        out.append({'titulo': titulo, 'medio': medio, 'url': H.unescape(g('link')).strip(), 'fecha': fecha.strftime('%Y-%m-%d')})
    out.sort(key=lambda x: x['fecha'], reverse=True)
    return out[:40]


ELEGIR_SIS = """Eres editor de CORILLO, comunidad gamer de Puerto Rico. Te doy titulares numerados de prensa sobre Battlefield 6.
Varios medios cuentan la misma noticia con palabras distintas. Agrúpalos por noticia y escoge UN titular por noticia (el más
claro e informativo, preferiblemente de un medio conocido). Descarta lo que no sea de Battlefield 6, rumores sin fuente,
listas de ofertas genéricas y titulares sensacionalistas. Devuelve los números escogidos, de la noticia más importante para
un jugador a la menos, como máximo %d.""" % PRENSA_MAX


def elegir_prensa(cliente, cands: list[dict]) -> list[dict]:
    lista = '\n'.join(f"{i}. [{c['fecha']}] {c['titulo']} ({c['medio']})" for i, c in enumerate(cands))
    msg = cliente.beta.messages.create(
        model=MODELO, max_tokens=2000,
        betas=['server-side-fallback-2026-07-01'], fallbacks='default',
        output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': {
            'type': 'object', 'properties': {'escogidos': {'type': 'array', 'items': {'type': 'integer'}}},
            'required': ['escogidos'], 'additionalProperties': False}}},
        system=ELEGIR_SIS, messages=[{'role': 'user', 'content': lista}],
    )
    if msg.stop_reason == 'refusal':
        raise RuntimeError('refusal')
    log(f'  prensa {msg.model}: in={msg.usage.input_tokens} out={msg.usage.output_tokens}')
    idx = json.loads(''.join(b.text for b in msg.content if b.type == 'text'))['escogidos']
    vistos = []
    for i in idx:
        if isinstance(i, int) and 0 <= i < len(cands) and i not in vistos:
            vistos.append(i)
    return [cands[i] for i in vistos][:PRENSA_MAX]


def _lockups(o, out):
    if isinstance(o, dict):
        if 'lockupViewModel' in o:
            out.append(o['lockupViewModel'])
            return
        for x in o.values():
            _lockups(x, out)
    elif isinstance(o, list):
        for x in o:
            _lockups(x, out)


def _textos(o) -> list[str]:
    if isinstance(o, dict):
        r = [o['content']] if isinstance(o.get('content'), str) else []
        return r + [t for x in o.values() for t in _textos(x)]
    if isinstance(o, list):
        return [t for x in o for t in _textos(x)]
    return []


def videos_youtube(handle: str, pestana: str) -> list[dict]:
    h = httpx.get(f'https://www.youtube.com/@{handle}/{pestana}', headers=NAVEGADOR, timeout=20, follow_redirects=True).text
    m = re.search(r'var ytInitialData = (\{.*?\});</script>', h, re.S)
    if not m:
        raise RuntimeError('sin ytInitialData')
    crudos = []
    _lockups(json.loads(m.group(1)), crudos)
    out = []
    for v in crudos:
        vid = v.get('contentId')
        meta = v.get('metadata', {}).get('lockupMetadataViewModel', {})
        titulo = (meta.get('title') or {}).get('content')
        if not vid or not titulo or not re.fullmatch(r'[\w-]{11}', vid):
            continue
        filas = _textos(meta.get('metadata', {}))
        insignias = json.dumps(v.get('contentImage', {}))
        out.append({'id': vid, 'titulo': titulo.strip(), 'detalle': ' · '.join(t for t in filas if t and t != titulo)[:80],
                    'vivo': 'BADGE_STYLE_LIVE' in insignias, 'directo': pestana == 'streams'})
    return out


def canal(c: dict, previo: dict | None) -> dict:
    try:
        lista = videos_youtube(c['handle'], 'streams')
        ids = {v['id'] for v in lista}
        lista += [v for v in videos_youtube(c['handle'], 'videos') if v['id'] not in ids]
        if not lista:
            raise RuntimeError('ningún video en la página')
    except Exception as e:
        log(f"  YouTube @{c['handle']} falló: {type(e).__name__}: {str(e)[:120]} — queda lo de antes")
        return previo or {**c, 'videos': [], 'en_vivo': None}
    vivo = next((v['id'] for v in lista if v['vivo']), None)
    return {**c, 'url': f"https://www.youtube.com/@{c['handle']}", 'en_vivo': vivo, 'videos': lista[:8]}


def resumir(cliente, titulo: str, cuerpo: str) -> dict:
    msg = cliente.beta.messages.create(
        model=MODELO, max_tokens=2000,
        betas=['server-side-fallback-2026-07-01'], fallbacks='default',
        output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': ESQUEMA}},
        system=SISTEMA,
        messages=[{'role': 'user', 'content': f'Título: {titulo}\n\nAnuncio:\n{cuerpo[:12000]}'}],
    )
    if msg.stop_reason == 'refusal':
        raise RuntimeError('refusal')
    txt = ''.join(b.text for b in msg.content if b.type == 'text')
    log(f'  {msg.model}: in={msg.usage.input_tokens} out={msg.usage.output_tokens}')
    d = json.loads(txt)
    return {'titulo': d['titulo'].strip()[:90], 'resumen': d['resumen'].strip()[:300]}


def main() -> int:
    sin_ia = '--sin-ia' in sys.argv
    viejo = json.loads(DATOS.read_text()) if DATOS.exists() else {'noticias': []}
    hechos = {n['gid']: n for n in viejo.get('noticias', [])}
    try:
        lista = anuncios()
    except Exception as e:
        log(f'Steam falló: {type(e).__name__}: {e} — no se toca {DATOS.name}')
        return 1
    if not lista:
        log('Steam no devolvió anuncios — no se toca nada')
        return 1

    cliente = None
    if not sin_ia:
        cargar_llaves()
        import anthropic
        cliente = anthropic.Anthropic()

    nuevas = 0
    salida = []
    for n in lista:
        gid = str(n['gid'])
        previa = hechos.get(gid)
        if previa and (previa.get('resumen') or sin_ia):
            salida.append(previa)
            continue
        item = {
            'gid': gid,
            'fecha': datetime.fromtimestamp(n['date'], timezone.utc).strftime('%Y-%m-%d'),
            'titulo_original': n['title'].strip(),
            'url': n['url'],
            'imagen': primera_imagen(n.get('contents', '')),
            'titulo': n['title'].strip(), 'resumen': '',
        }
        if cliente:
            try:
                item.update(resumir(cliente, n['title'], texto_plano(n.get('contents', ''))))
                nuevas += 1
            except Exception as e:
                log(f'  resumen falló para {gid}: {type(e).__name__}: {str(e)[:160]} — queda el título original')
        salida.append(item)

    try:
        cands = prensa()
        firma = sorted(c['url'] for c in cands)
        if firma == viejo.get('prensa_firma'):
            titulares = viejo.get('prensa', [])          # nada nuevo en Google News: no se gasta otra consulta
        elif viejo.get('prensa') and viejo.get('prensa_hora') and \
                (datetime.now(timezone.utc) - datetime.fromisoformat(viejo['prensa_hora'])).total_seconds() < PRENSA_HORAS * 3600:
            titulares, firma = viejo['prensa'], viejo.get('prensa_firma')
        elif cliente:
            titulares = elegir_prensa(cliente, cands)
        else:
            titulares = cands[:PRENSA_MAX]
    except Exception as e:
        log(f'prensa falló: {type(e).__name__}: {str(e)[:120]} — quedan los titulares de antes')
        titulares, firma = viejo.get('prensa', []), viejo.get('prensa_firma')
    prensa_hora = viejo.get('prensa_hora') if firma == viejo.get('prensa_firma') else datetime.now(timezone.utc).isoformat(timespec='seconds')
    previos = {c.get('handle'): c for c in viejo.get('canales', [])}
    canales = [canal(c, previos.get(c['handle'])) for c in CANALES]

    datos = {'actualizado': datetime.now(timezone.utc).isoformat(timespec='seconds'),
             'noticias': salida, 'prensa': titulares, 'prensa_firma': firma, 'prensa_hora': prensa_hora, 'canales': canales}
    if all(datos[k] == viejo.get(k) for k in ('noticias', 'prensa', 'canales')):
        log('sin cambios')
        return 0
    DATOS.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n')
    log(f'{len(salida)} anuncios ({nuevas} resumidos ahora), {len(titulares)} titulares, ' + ', '.join(f"@{c['handle']}: {len(c['videos'])} videos{' (EN VIVO)' if c.get('en_vivo') else ''}" for c in canales))
    return 0


if __name__ == '__main__':
    sys.exit(main())
