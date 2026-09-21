#!/home/corillo-adm/corillo-news/venv/bin/python
"""Noticia diaria de CORILLO.

Flujo: RSS (descubrir) -> Claude elige UNA noticia que valga la pena (o ninguna) -> lee 2-4 fuentes ->
Claude redacta una nota ORIGINAL en español -> Claude + comprobación programática verifican que los
datos salen de las fuentes y que no hay texto copiado -> escribe el .md, despliega, commit y avisa por Telegram.

Uso:
  daily-news.py                  # corrida normal (cron): máx. 1 nota al día
  daily-news.py --dry-run        # hace todo menos escribir/desplegar; imprime el resultado
  daily-news.py --backfill 3     # publica hasta 3 notas seguidas (para arrancar); ignora el tope diario
  daily-news.py --unpublish SLUG # retira una nota (borra el .md, despliega, commit)

Nunca publica basura, pero tampoco se rinde a la primera: verifica que la noticia sea real ANTES de escribir, escribe solo con hechos verificados,
y si un tema no se sostiene prueba con otro (hasta MAX_STORIES). Solo no publica si el selector no ve nada (MIN_SCORE) o se agotan los temas.
"""
import argparse, datetime as dt, difflib, hashlib, html, json, os, re, subprocess, sys, time, unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import anthropic, feedparser, httpx

REPO = Path('/var/www/stream')
POSTS = REPO / 'src/content/noticias'
CFG = json.loads((REPO / 'scripts/news_sources.json').read_text())
HOME = Path('/home/corillo-adm/corillo-news')
LOGS = HOME / 'logs'; LOGS.mkdir(parents=True, exist_ok=True)
STATE = HOME / 'state.json'
PROVIDER = None  # 'deepseek' | 'anthropic'; se decide en main() según las llaves disponibles (NEWS_PROVIDER lo fuerza)
MODEL = os.environ.get('NEWS_MODEL', 'claude-opus-5')
DS_MODEL = os.environ.get('NEWS_DS_MODEL', 'deepseek-v4-pro')
FALLBACK_MODEL = 'claude-opus-4-8'
MIN_SCORE = 7
UA = 'CorilloNewsBot/1.0 (+https://corillo.live/noticias/; hello@marcossantiago.com)'
WINDOW_H = 40
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
CATS = {  # espejo de src/data/news.ts
    'gaming': ('Gaming y esports', 'fa-solid fa-gamepad', 'badge-confirm'),
    'tech': ('Tecnología e IA', 'fa-solid fa-microchip', 'badge-accent'),
    'streaming': ('Streaming y creadores', 'fa-solid fa-tower-broadcast', 'badge-confirm'),
    'geek': ('Cultura geek', 'fa-solid fa-wand-magic-sparkles', 'badge-accent'),
    'pr': ('Puerto Rico', 'fa-solid fa-flag', 'badge-accent'),
}

def log(*a):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} " + ' '.join(str(x) for x in a)
    print(line, flush=True)

def load_env():
    for f in ('/home/corillo-adm/corillo-news/.env', '/home/corillo-adm/corillo-bot/.env', '/home/corillo-adm/corillo-telegram/.env'):
        if not Path(f).exists(): continue
        for l in Path(f).read_text().splitlines():
            if '=' in l and not l.startswith('#'):
                k, v = l.split('=', 1); os.environ.setdefault(k.strip(), v.strip().strip('"\''))

def telegram(msg):
    try:
        httpx.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                   data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'text': msg, 'disable_web_page_preview': 'true'}, timeout=15)
    except Exception as e:
        log('telegram falló:', e)

# ───────────── estado / publicadas ─────────────
def published():
    out = []
    for f in sorted(POSTS.glob('*.md')):
        t = f.read_text()
        title = (re.search(r'^heroTitle:\s*"(.*)"\s*$', t, re.M) or re.search(r'^title:\s*"(.*)"\s*$', t, re.M))
        urls = re.findall(r'^\s+url:\s*"(.*)"\s*$', t, re.M)
        pd = re.search(r'^pubDate:\s*(\S+)', t, re.M); ct = re.search(r'^category:\s*"(\w+)"', t, re.M)
        out.append({'file': f.name, 'title': title.group(1) if title else f.stem, 'urls': urls, 'pd': pd.group(1) if pd else f.name[:10], 'cat': ct.group(1) if ct else 'corillo'})
    return sorted(out, key=lambda x: x['pd'])  # por fecha real (no por nombre de archivo)

def state():
    try: return json.loads(STATE.read_text())
    except Exception: return {'seen': {}}

def save_state(s):
    cutoff = time.time() - 14 * 86400
    s['seen'] = {k: v for k, v in s['seen'].items() if v > cutoff}
    STATE.write_text(json.dumps(s))

def norm(t):
    t = unicodedata.normalize('NFKD', t.lower()); t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]+', ' ', t).split()

# ───────────── descubrir ─────────────
def discover(exclude_urls):
    cutoff = time.time() - WINDOW_H * 3600
    kw = re.compile(CFG['kw_regex'], re.I)
    items, seen_t = [], []
    for f in CFG['feeds']:
        try:
            r = httpx.get(f['url'], headers={'User-Agent': UA}, timeout=15, follow_redirects=True)
            d = feedparser.parse(r.content)
        except Exception as e:
            log('feed falló', f['name'], type(e).__name__); continue
        n = 0
        for e in d.entries[:40]:
            ts = e.get('published_parsed') or e.get('updated_parsed')
            if ts and time.mktime(ts) < cutoff - 3600 * 8: continue  # (mktime local vs UTC: margen de 8 h)
            title = html.unescape(e.get('title', '')).strip(); link = e.get('link', '')
            summ = re.sub(r'<[^>]+>', ' ', html.unescape(e.get('summary', ''))); summ = re.sub(r'\s+', ' ', summ).strip()[:400]
            if not title or not link or link in exclude_urls: continue
            if f.get('kw') and not kw.search(title + ' ' + summ): continue
            key = ' '.join(norm(title)[:8])
            if any(difflib.SequenceMatcher(None, key, s).ratio() > .85 for s in seen_t): continue
            seen_t.append(key); n += 1
            items.append({'source': f['name'], 'cat': f['cat'], 'title': title, 'url': link, 'summary': summ})
        log(f"feed {f['name']}: {n}")
    for i, it in enumerate(items): it['id'] = i
    return items

# ───────────── Claude ─────────────
def _check(obj, schema, path='$'):
    """Validación mínima del esquema (DeepSeek solo garantiza 'JSON válido', no el esquema)."""
    t = schema.get('type'); ts = t if isinstance(t, list) else [t]
    ok = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool, 'null': type(None)}
    if not any(isinstance(obj, ok[x]) and not (x == 'integer' and isinstance(obj, bool)) for x in ts): raise ValueError(f'{path}: tipo inválido')
    if 'enum' in schema and obj not in schema['enum']: raise ValueError(f'{path}: valor fuera de enum')
    if isinstance(obj, dict):
        for k in schema.get('required', []):
            if k not in obj: raise ValueError(f'{path}.{k}: falta')
        for k, sub in schema.get('properties', {}).items():
            if k in obj: _check(obj[k], sub, f'{path}.{k}')
    if isinstance(obj, list) and 'items' in schema:
        for i, x in enumerate(obj): _check(x, schema['items'], f'{path}[{i}]')

def deepseek_json(system, user, schema, max_tokens=8000, think=False):
    key = os.environ['DEEPSEEK_API_KEY']
    sys_p = system + '\n\nResponde SOLO con un objeto json (sin texto extra ni markdown) que cumpla este esquema json:\n' + json.dumps(schema, ensure_ascii=False)
    last = None
    for attempt in range(3):  # la API a veces devuelve contenido vacío con json_object
        try:
            body = {'model': DS_MODEL, 'max_tokens': max_tokens, 'stream': False, 'response_format': {'type': 'json_object'},
                    'thinking': {'type': 'enabled' if think else 'disabled'},
                    'messages': [{'role': 'system', 'content': sys_p}, {'role': 'user', 'content': user}]}
            if not think: body['temperature'] = 0.4
            r = httpx.post('https://api.deepseek.com/chat/completions', headers={'Authorization': f'Bearer {key}'}, json=body, timeout=240)
            r.raise_for_status(); d = r.json(); ch = d['choices'][0]
            if ch.get('finish_reason') == 'length': raise RuntimeError('respuesta cortada por max_tokens')
            txt = (ch['message'].get('content') or '').strip()
            if not txt: raise RuntimeError('contenido vacío')
            obj = json.loads(txt); _check(obj, schema)
            u = d.get('usage', {}); log(f"  {DS_MODEL}: in={u.get('prompt_tokens')} out={u.get('completion_tokens')}")
            return obj
        except Exception as e:
            last = e; log(f'  {DS_MODEL} intento {attempt + 1} falló: {type(e).__name__}: {str(e)[:160]}'); time.sleep(3)
    raise last

def llm_json(client, system, user, schema, max_tokens=8000, think=False):
    if PROVIDER == 'deepseek': return deepseek_json(system, user, schema, max_tokens, think)
    return claude_json(client, system, user, schema, max_tokens)

def claude_json(client, system, user, schema, max_tokens=8000):
    last = None
    for model in (MODEL, FALLBACK_MODEL):
        try:
            with client.messages.stream(
                model=model, max_tokens=max_tokens, thinking={'type': 'adaptive'}, system=system,
                messages=[{'role': 'user', 'content': user}],
                output_config={'format': {'type': 'json_schema', 'schema': schema}},
            ) as s:
                m = s.get_final_message()
            if m.stop_reason == 'refusal': raise RuntimeError('refusal')
            txt = ''.join(b.text for b in m.content if b.type == 'text')
            log(f"  {model}: in={m.usage.input_tokens} out={m.usage.output_tokens}")
            return json.loads(txt)
        except Exception as e:
            last = e; log(f'  {model} falló: {type(e).__name__}: {str(e)[:160]}')
    raise last

SEL_SYS = """Eres el editor de CORILLO (corillo.live), una plataforma independiente de streaming de Puerto Rico con comunidad gamer.
Línea editorial: gaming y esports; tecnología e IA que importa a gamers y creadores; streaming y creación de contenido;
cultura geek y entretenimiento (cine, series, anime, cómics); y noticias de Puerto Rico en esas áreas.
Tu trabajo: de la lista de titulares recientes, escoger LA noticia que de verdad valga la pena para esa audiencia hispana,
o ninguna. Criterios: relevancia real para la comunidad, hecho concreto y verificable (no rumor ni clickbait), novedad,
que se pueda explicar aportando contexto útil. Descarta ofertas/cupones, listas de "mejores X", reseñas de producto,
política general, crónica roja y notas que ya cubrimos. Descarta también muertes, enfermedades o tragedias personales (sobre todo de menores), escándalos y chismes de famosos: no somos un medio de sucesos. Busca variedad: si las últimas notas fueron de videojuegos, prefiere cine/series, tecnología/IA, streaming o Puerto Rico cuando haya una historia igual de buena. Prefiere historias con varias fuentes independientes.
Puntúa 1-10 (10 = imperdible). Si nada llega a 7, devuelve choice_id null."""
SEL_SCHEMA = {'type': 'object', 'additionalProperties': False,
    'required': ['choice_id', 'score', 'category', 'angle', 'related_ids', 'reason'],
    'properties': {'choice_id': {'type': ['integer', 'null']}, 'score': {'type': 'integer'},
        'category': {'type': 'string', 'enum': list(CATS)}, 'angle': {'type': 'string'},
        'related_ids': {'type': 'array', 'items': {'type': 'integer'}}, 'reason': {'type': 'string'}}}

WRITE_SYS = """Eres redactor de CORILLO, una plataforma de streaming de Puerto Rico. Escribes en español natural y cercano (neutro con calidez
boricua, sin jerga forzada), para gamers y creadores. Redactas una nota ORIGINAL a partir de las fuentes que te doy.
Reglas estrictas:
- Usa SOLO hechos que aparezcan en las fuentes (cifras, fechas, nombres, citas). No inventes ni especules; si algo no está claro, dilo o déjalo fuera.
- Redacta con tus propias palabras y tu propia estructura. Prohibido copiar o parafrasear de cerca frases de las fuentes; las citas textuales, máximo una y corta (<15 palabras), entre comillas y atribuida.
- Aporta valor: qué pasó, por qué importa a la comunidad de CORILLO, qué sigue. Una sección 'Por qué importa' concreta.
- Longitud del cuerpo: 350-550 palabras. Markdown: párrafos, 2-3 subtítulos ## como máximo, sin H1, sin listas de relleno, sin emoji.
- Título informativo (máx. 90 caracteres), sin clickbait ni mayúsculas gritonas. No menciones que eres una IA en el texto (el sitio ya lo avisa).
- El extracto (description) máx. 160 caracteres. summary: 1-2 frases para la tarjeta. heroSub: una frase de apoyo.
- tags: 3-5 etiquetas cortas. sources_used: índices (empezando en 0) de las fuentes de las que realmente sacaste datos.
- Te doy una HOJA DE HECHOS VERIFICADOS: escribe SOLO con esos hechos. No conectes hechos entre sí con causas, motivos o consecuencias que la hoja no diga, y no afirmes nada de la lista NO ESTABLECIDO.
- Si te dan 'problemas' de un intento anterior, corrígelos todos (quita o reformula la frase problemática; nunca la reemplaces por otra sin respaldo)."""
WRITE_SCHEMA = {'type': 'object', 'additionalProperties': False,
    'required': ['title', 'description', 'summary', 'heroSub', 'body', 'category', 'tags', 'sources_used'],
    'properties': {k: {'type': 'string'} for k in ('title', 'description', 'summary', 'heroSub', 'body')} | {
        'category': {'type': 'string', 'enum': list(CATS)},
        'tags': {'type': 'array', 'items': {'type': 'string'}},
        'sources_used': {'type': 'array', 'items': {'type': 'integer'}}}}

FACTS_SYS = """Eres el verificador de autenticidad de una redacción. Recibes textos de fuentes sobre un mismo tema. ANTES de que nadie escriba nada,
decide si es una NOTICIA REAL: un hecho concreto y reportado (anuncio oficial, dato, evento, lanzamiento, resultado, decisión, estudio) y NO un rumor,
una filtración sin confirmar, sátira, opinión, clickbait, contenido promocional o algo sin sustancia.
Luego extrae la HOJA DE HECHOS: afirmaciones atómicas que aparecen en las fuentes (cifras, fechas, nombres, cargos, lugares, citas cortas literales),
cada una con los índices de las fuentes que la respaldan. corroborated=true solo si 2 o más fuentes independientes coinciden en ella.
Aparte, en not_established, lista las relaciones causales, motivos, consecuencias, comparaciones o especulaciones que las fuentes NO establecen
y que una nota no debe afirmar como hecho. Sé estricto: copia solo lo que está en los textos."""
FACTS_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['real', 'kind', 'reason', 'facts', 'not_established'],
    'properties': {'real': {'type': 'boolean'}, 'kind': {'type': 'string', 'enum': ['oficial', 'confirmado', 'rumor', 'opinion', 'promocional', 'otro']},
        'reason': {'type': 'string'},
        'facts': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['claim', 'sources', 'corroborated'],
            'properties': {'claim': {'type': 'string'}, 'sources': {'type': 'array', 'items': {'type': 'integer'}}, 'corroborated': {'type': 'boolean'}}}},
        'not_established': {'type': 'array', 'items': {'type': 'string'}}}}

VER_SYS = """Eres verificador de hechos de una redacción. Recibes una nota y los textos de las fuentes. Clasifica cada problema que encuentres:
- severity "grave": un dato concreto (cifra, fecha, nombre, cargo, lugar, cita, lanzamiento) que NO está respaldado por ninguna fuente o las contradice;
  una relación causal, motivo o consecuencia que ninguna fuente establece; o una especulación presentada como hecho.
- severity "menor": estilo, tono, un título algo enfático, matices de redacción, contexto general obvio que no cambia ningún hecho.
ok = true si NO hay problemas graves (los menores no bloquean). Sé estricto con los datos y tolerante con el estilo. Cada problema debe ser concreto:
cita la frase de la nota y explica qué falta o qué dicen realmente las fuentes."""
VER_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['ok', 'problems'],
    'properties': {'ok': {'type': 'boolean'}, 'problems': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
        'required': ['text', 'severity'], 'properties': {'text': {'type': 'string'}, 'severity': {'type': 'string', 'enum': ['grave', 'menor']}}}}}}
MAX_STORIES = 4   # temas que se prueban en un día antes de rendirse (peor caso ~US$0.4)

# ───────────── leer fuentes ─────────────
class _Text(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'svg', 'iframe', 'button'}
    def __init__(self):
        super().__init__(); self.buf, self.skip, self.in_p = [], 0, 0
    def handle_starttag(self, t, a):
        if t in self.SKIP: self.skip += 1
        if t == 'p': self.in_p += 1
    def handle_endtag(self, t):
        if t in self.SKIP and self.skip: self.skip -= 1
        if t == 'p' and self.in_p: self.in_p -= 1; self.buf.append('\n')
    def handle_data(self, d):
        if not self.skip and self.in_p and len(d.strip()) > 1: self.buf.append(d)

_robots = {}
def allowed(url):
    o = urlparse(url); base = f'{o.scheme}://{o.netloc}'
    if base not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = httpx.get(base + '/robots.txt', headers={'User-Agent': UA}, timeout=8, follow_redirects=True)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception: rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch('CorilloNewsBot', url)

def fetch_text(url):
    if not allowed(url): log('  robots.txt no permite', url); return ''
    try:
        r = httpx.get(url, headers={'User-Agent': UA}, timeout=20, follow_redirects=True)
        if r.status_code != 200: return ''
        p = _Text(); p.feed(r.text)
        t = re.sub(r'[ \t]+', ' ', ''.join(p.buf)); t = re.sub(r'\n\s*\n+', '\n', t).strip()
        return t[:9000]
    except Exception as e:
        log('  fetch falló', url, type(e).__name__); return ''

# ───────────── comprobación de copia ─────────────
def copied_ratio(article, sources, n=10):
    def shingles(t):
        w = norm(t); return {' '.join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}
    a = shingles(article)
    if not a: return 0.0
    s = set().union(*[shingles(x) for x in sources]) if sources else set()
    return len(a & s) / len(a)

# ───────────── escribir el post ─────────────
def slugify(t):
    w, out = norm(t), ''
    for x in w:
        if len(out) + len(x) + 1 > 70: break
        out += ('-' if out else '') + x
    return out or 'nota'

def yq(s): return json.dumps(s, ensure_ascii=False)

def build_md(a, srcs, now):
    cat = a['category']; label, icon, badge = CATS[cat]
    used = [srcs[i] for i in a['sources_used'] if 0 <= i < len(srcs)] or srcs
    fm = ['---', f"title: {yq('CORILLO — Noticias · ' + a['title'])}", f"description: {yq(a['description'])}",
          f"ogTitle: {yq(a['title'])}", f"ogDescription: {yq(a['description'])}", f'badgeClass: "{badge}"', f'badgeIcon: "{icon}"',
          f'badgeLabel: {yq(label)}', f'date: "{now.day} {MESES[now.month - 1]} {now.year}"', f'pubDate: {now:%Y-%m-%dT%H:%M:%SZ}',
          f"heroTitle: {yq(a['title'])}", f"heroSub: {yq(a['heroSub'])}", f"summary: {yq(a['summary'])}", f'category: "{cat}"',
          f"tags: {json.dumps(a['tags'][:5], ensure_ascii=False)}", 'ai: true', 'sources:']
    for s in used: fm += [f"  - name: {yq(s['source'])}", f"    url: {yq(s['url'])}"]
    fm.append('---')
    return '\n'.join(fm) + '\n\n' + a['body'].strip() + '\n'

def sh(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, **kw)

def deploy():
    r = sh(['bash', 'scripts/deploy-corillo.sh'])
    log('deploy', 'OK' if r.returncode == 0 else 'FALLÓ');
    if r.returncode: log(r.stdout[-800:], r.stderr[-800:])
    return r.returncode == 0

def git_publish(files, msg):
    try:
        sh(['git', 'add', '--'] + [str(f) for f in files])
        c = sh(['git', 'commit', '-m', msg + '\n\n[skip ci]\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>'])
        if c.returncode: log('commit:', c.stderr[-300:]); return
        p = sh(['git', 'push', 'origin', 'HEAD'], timeout=90)
        log('push', 'OK' if p.returncode == 0 else 'falló (queda commit local): ' + p.stderr[-200:])
    except Exception as e:
        log('git falló (no bloquea):', e)

# ───────────── una nota ─────────────
def pick_story(client, items, used_ids, pub):
    """Elige un tema y lee sus fuentes. None = no hay nada elegible (parar); False = este tema no sirve (probar otro)."""
    recent = '\n'.join(f"- [{p['cat']}] {p['title']}" for p in pub[-20:])
    lst = '\n'.join(f"[{i['id']}] ({i['source']}/{i['cat']}) {i['title']} — {i['summary'][:220]}" for i in items if i['id'] not in used_ids)
    STOP = set('nuevo nueva nuevos nuevas juego juegos millones anuncia revela lanza lanzamiento tras mil año años primer primera mejor todo todos para como sobre tras esta este esto pero desde entre hasta cuando donde porque sus los las del una uno con por que the and for with from'.split())
    def toks(t): return {w for w in norm(t) if len(w) > 3 and w not in STOP}
    recent_t = [toks(p['title']) for p in pub[-10:]]
    def repeats(cands):  # ¿mismo tema que algo ya publicado? (solapamiento de palabras clave)
        c = toks(cands)
        return any(len(c & r) >= 2 and len(c & r) / max(1, min(len(c), len(r))) >= 0.2 for r in recent_t)
    sel = None
    for _try in range(3):
        avail = [i for i in items if i['id'] not in used_ids]
        lst = '\n'.join(f"[{i['id']}] ({i['source']}/{i['cat']}) {i['title']} — {i['summary'][:220]}" for i in avail)
        sel = llm_json(client, SEL_SYS, f"Notas que CORILLO ya publicó (NO repetir estos temas ni sus variantes, aunque venga de otra fuente):\n{recent}\n\nTitulares de las últimas {WINDOW_H} horas:\n{lst}\n\nElige.", SEL_SCHEMA, 8000)
        log('selector:', json.dumps(sel, ensure_ascii=False)[:400])
        cid = sel['choice_id']
        if cid is None or sel['score'] < MIN_SCORE: break
        it = next((i for i in items if i['id'] == cid), None)
        if it and repeats(it['title'] + ' ' + sel['angle']):
            log('tema ya cubierto, se descarta y se vuelve a elegir:', it['title']); used_ids.add(cid); sel = None; continue
        break
    if sel is None: log('todo lo elegible repite temas ya publicados: no se publica'); return None
    byid = {i['id']: i for i in items}
    if sel['choice_id'] not in byid: return None
    used_ids.add(sel['choice_id'])
    chosen = [byid[sel['choice_id']]] + [byid[r] for r in sel['related_ids'] if r in byid and r != sel['choice_id']][:3]
    srcs, texts = [], []
    for c in chosen:
        t = fetch_text(c['url'])
        if len(t) < 500: t = c['title'] + '. ' + c['summary']  # solo el resumen del feed si la página no sirve
        if len(t) > 200: srcs.append(c); texts.append(t)
    full = [t for t in texts if len(t) > 800]
    if not full: log('ninguna fuente legible con suficiente texto: se descarta el tema'); return False
    log('fuentes:', [s['source'] for s in srcs])
    block = '\n\n'.join(f"=== FUENTE {i}: {s['source']} — {s['title']} ({s['url']}) ===\n{t}" for i, (s, t) in enumerate(zip(srcs, texts)))
    return sel, srcs, texts, block, [c['id'] for c in chosen]

def trim_desc(t, n=160):
    """Recorta el extracto a n caracteres sin dejarlo colgando: prefiere terminar en una frase completa
    y, si no, en el límite de una palabra que no sea conector ("con", "de", "y"…)."""
    if len(t) <= n: return t
    cut = t[:n - 1]
    m = max(cut.rfind('. '), cut.rfind('; '))
    if m >= 70: return cut[:m + 1]
    words = cut.rsplit(' ', 1)[0].split(' ')
    while len(words) > 3 and words[-1].lower().strip(',;:') in {'con', 'de', 'del', 'y', 'e', 'o', 'a', 'al', 'en', 'el', 'la', 'los', 'las', 'un', 'una', 'que', 'para', 'por', 'su', 'sus', 'tras', 'como', 'se', 'sobre'}:
        words.pop()
    return ' '.join(words).rstrip(' ,;:—-') + '…'

def write_story(client, sel, srcs, texts, block):
    """Verificar primero, escribir después. Devuelve (nota, fuentes) o None si el tema no se sostiene."""
    facts = llm_json(client, FACTS_SYS, f"Tema: {sel['angle']}\n\n{block}", FACTS_SCHEMA, 12000, think=True)
    log(f"autenticidad: real={facts['real']} tipo={facts['kind']} hechos={len(facts['facts'])} corroborados={sum(1 for x in facts['facts'] if x['corroborated'])} — {facts['reason'][:220]}")
    if not (facts['real'] and facts['kind'] in ('oficial', 'confirmado') and len(facts['facts']) >= 4):
        log('no pasa la verificación de autenticidad: se descarta el tema'); return None
    sheet = '\n'.join(f"- {x['claim']} [fuentes {','.join(str(i) for i in x['sources'])}]{' (corroborado)' if x['corroborated'] else ''}" for x in facts['facts'])
    notest = '\n'.join('- ' + x for x in facts['not_established']) or '- (nada en particular)'
    problems, art = [], None
    for attempt in (1, 2, 3):
        u = (f"Enfoque sugerido por el editor: {sel['angle']}\nCategoría sugerida: {sel['category']}\n\n"
             f"HOJA DE HECHOS VERIFICADOS (escribe solo con esto):\n{sheet}\n\nNO ESTABLECIDO (no lo afirmes):\n{notest}\n\nFuentes completas, solo como contexto:\n{block}")
        if problems: u += '\n\nProblemas del intento anterior a corregir:\n' + '\n'.join('- ' + p for p in problems)
        art = llm_json(client, WRITE_SYS, u, WRITE_SCHEMA, 10000)
        ratio = copied_ratio(art['body'], texts)
        words = len(art['body'].split())
        log(f"intento {attempt}: {words} palabras, copia={ratio:.1%}")
        blocking, soft = [], []
        if ratio > 0.04: blocking.append(f'Copia demasiado texto de las fuentes ({ratio:.0%}); reescribe con tus palabras.')
        if not 300 <= words <= 800: blocking.append(f'Longitud {words} palabras; debe ser 350-550.')
        if len(art['description']) > 160:  # cosmético: recortar en límite de palabra en vez de rechazar la nota
            art['description'] = trim_desc(art['description'])
        ver = llm_json(client, VER_SYS, f"NOTA:\nTítulo: {art['title']}\n{art['body']}\n\nHOJA DE HECHOS:\n{sheet}\n\n{block}", VER_SCHEMA, 12000, think=True)
        for p in ver['problems']:
            t, sev = (p['text'], p['severity']) if isinstance(p, dict) else (str(p), 'grave')
            (blocking if sev == 'grave' else soft).append(t)
        if soft: log('reparos menores (no bloquean):', soft)
        if not blocking:
            art['category'] = art['category'] if art['category'] in CATS else sel['category']
            return art, srcs
        log('problemas graves:', blocking)
        problems = blocking + soft
    log('este tema no se pudo redactar sin errores tras 3 intentos'); return None

def make_one(client, items, used_ids, pub, dry):
    """Prueba temas hasta que uno pase; solo se rinde si se agotan MAX_STORIES temas."""
    for n in range(1, MAX_STORIES + 1):
        st = pick_story(client, items, used_ids, pub)
        if st is None: return None
        if st is not False:
            sel, srcs, texts, block, ids = st
            r = write_story(client, sel, srcs, texts, block)
            if r: return r
            used_ids.update(ids)      # tampoco volver a intentar las fuentes relacionadas del mismo hecho
        log(f'tema descartado ({n}/{MAX_STORIES}); se prueba con otro')
    log(f'se agotaron los {MAX_STORIES} temas del día: no se publica'); return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--backfill', type=int, default=0)
    ap.add_argument('--unpublish'); a = ap.parse_args()
    load_env()

    if a.unpublish:
        f = POSTS / (a.unpublish if a.unpublish.endswith('.md') else a.unpublish + '.md')
        if not f.exists(): sys.exit(f'no existe {f}')
        f.unlink(); ok = deploy(); git_publish([f], f'noticias: retirar {f.stem}')
        telegram(f'🗑️ Nota retirada: {f.stem}'); sys.exit(0 if ok else 1)

    now = dt.datetime.now(dt.timezone.utc)
    pub = published()
    today = f'{now:%Y-%m-%d}'
    hoy = dt.datetime.now().strftime('%Y-%m-%d')
    if not a.backfill and not a.dry_run and any(p['file'].startswith(hoy) and 'ai: true' in (POSTS / p['file']).read_text() for p in pub):
        log('ya hay nota automática de hoy'); return
    global PROVIDER
    PROVIDER = os.environ.get('NEWS_PROVIDER') or ('deepseek' if os.environ.get('DEEPSEEK_API_KEY') else 'anthropic')
    log('proveedor:', PROVIDER, DS_MODEL if PROVIDER == 'deepseek' else MODEL)
    client = anthropic.Anthropic() if PROVIDER == 'anthropic' else None
    exclude = {u for p in pub for u in p['urls']}
    items = discover(exclude)
    st = state(); items = [i for i in items if hashlib.md5(i['url'].encode()).hexdigest() not in st['seen']]
    log(f'{len(items)} candidatos')
    if len(items) < 5: log('muy pocos candidatos'); telegram('⚠️ Noticias: muy pocos candidatos hoy (¿feeds caídos?)'); return

    n = max(1, a.backfill); made, used = [], set()
    for _ in range(n):
        try: r = make_one(client, items, used, pub, a.dry_run)
        except Exception as e:
            log('ERROR', type(e).__name__, e); telegram(f'⚠️ Noticias: error del pipeline: {type(e).__name__}: {str(e)[:200]}'); break
        if not r: break
        art, srcs = r
        md = build_md(art, srcs, now + dt.timedelta(minutes=len(made)))
        fname = f"{dt.datetime.now():%Y-%m-%d}-{slugify(art['title'])}.md"
        if a.dry_run:
            print('\n' + '=' * 70 + f'\n{fname}\n' + '=' * 70 + f'\n{md}')
            made.append(fname); continue
        (POSTS / fname).write_text(md); made.append(fname)
        pub.append({'file': fname, 'title': art['title'], 'urls': [s['url'] for s in srcs]})
        for s in srcs: st['seen'][hashlib.md5(s['url'].encode()).hexdigest()] = time.time()
    if a.dry_run or not made:
        if not made:
            log('hoy no se publica nada')
            if not a.dry_run: telegram('⚠️ Noticias: hoy NO se publicó ninguna nota (el verificador rechazó todos los borradores). Detalle en ~/corillo-news/logs/daily.log')
        save_state(st) if not a.dry_run else None; return
    save_state(st)
    if not deploy():
        for f in made: (POSTS / f).unlink(missing_ok=True)
        telegram('❌ Noticias: el build falló con la nota nueva; se retiró y el sitio quedó como estaba.'); sys.exit(1)
    git_publish([POSTS / f for f in made], 'noticias: ' + ', '.join(m[11:-3] for m in made)[:100])
    for f in made:
        t = re.search(r'^heroTitle: "(.*)"', (POSTS / f).read_text(), re.M).group(1)
        telegram(f"📰 Nota publicada en CORILLO:\n{t}\nhttps://corillo.live/noticias/{f[:-3]}/\n\nRetirar: daily-news.py --unpublish {f[:-3]}")

if __name__ == '__main__':
    main()
