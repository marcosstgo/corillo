"""Portada (imagen) de cada noticia de corillo.live.

Las notas de src/content/noticias/ no traían imagen. Copiar la foto del artículo fuente (IGN, GameSpot…) no es
nuestro y muchas son de Getty: riesgo de reclamo. Por eso cada nota busca su portada en este orden
(decisión de Marcos, 30-oct-2026, ver docs/rediseno-2026.md):

  1. arte oficial del juego en Steam (las compañías lo publican para promoción; es lo mismo que usa /ofertas/)
  2. ilustración generada con IA (Gemini), sin caras de personas reales — solo si hay GEMINI_API_KEY
  3. portada de diseño: color e ícono de la categoría + el título (siempre funciona)

Escribe public/noticias/portadas/<slug>.jpg (1600x900) y añade al frontmatter `image` e `imageCredit`.

Uso: python scripts/news_cover.py [--forzar] [--sin-ia] [--solo-diseno] notas.md...   (sin notas: las 9 más nuevas)
"""
import io, json, os, re, sys, unicodedata
from pathlib import Path
import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parent.parent
NOTAS = REPO / 'src' / 'content' / 'noticias'
SALIDA = REPO / 'public' / 'noticias' / 'portadas'
FONTS = Path(__file__).resolve().parent / 'fonts'
W, H = 1600, 900
INK, BONE, MUTE = (6, 20, 63), (245, 248, 255), (164, 182, 230)
CATS = {  # id: (etiqueta, color) — igual que src/data/news.ts
    'gaming': ('Gaming y esports', (255, 106, 61)), 'tech': ('Tecnología e IA', (255, 210, 63)),
    'streaming': ('Streaming y creadores', (53, 224, 161)), 'geek': ('Cultura geek', (139, 149, 255)),
    'pr': ('Puerto Rico', (122, 162, 255)), 'corillo': ('Plataforma', (255, 45, 85)),
}
HTTP = httpx.Client(timeout=25, follow_redirects=True, headers={'User-Agent': 'corillo.live news-cover'})


def frontmatter(path):
    t = path.read_text(encoding='utf-8')
    fm = t.split('---')[1]
    g = lambda k: (re.search(rf'^{k}:\s*(.*)$', fm, re.M) or [None, ''])[1].strip()
    titulo = re.sub(r'^CORILLO\s*[—-]\s*Noticias\s*·\s*', '', json.loads(g('title')) if g('title').startswith('"') else g('title'))
    try: tags = json.loads(g('tags') or '[]')
    except Exception: tags = []
    juego = g('game').strip('"\'') if g('game') else ''
    return t, fm, {'titulo': titulo, 'cat': g('category').strip('"\'') or 'corillo', 'tags': tags,
                   'juego': juego, 'resumen': g('description').strip('"\'')}


def _norm(s):
    s = re.sub(r'[™®©]', '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


ALIAS = {'cs2': 'Counter-Strike 2', 'gta6': 'Grand Theft Auto VI', 'gta 6': 'Grand Theft Auto VI', 'bf6': 'Battlefield 6',
         'cod': 'Call of Duty', 'lol': 'League of Legends', 'r6': 'Rainbow Six Siege'}


def steam(candidatos):
    """Primer candidato que es un juego en Steam → (jpeg, 'Arte oficial: <juego> (Steam)')."""
    for c in candidatos:
        c = ALIAS.get(c.lower(), c)
        if len(_norm(c)) < 3: continue
        try:
            r = HTTP.get('https://store.steampowered.com/api/storesearch/', params={'term': c, 'l': 'english', 'cc': 'US'}).json()
        except Exception: continue
        for it in r.get('items', [])[:5]:
            n, q = _norm(it['name']), _norm(c)
            # nombre exacto (o con año/edición): "Rockstar" no es "Rockstar Life", "Steam" no es "Steam Deck"
            if n == q or re.fullmatch(re.escape(q) + r' (\d{4}|legendary edition|remastered|definitive edition|goty edition|game of the year edition)', n):
                for f in ('library_hero.jpg', 'capsule_616x353.jpg', 'header.jpg'):
                    url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{it['id']}/{f}"
                    img = HTTP.get(url)
                    if img.status_code == 200 and img.headers.get('content-type', '').startswith('image'):
                        return img.content, f"Arte oficial: {it['name']} (Steam)"
    return None


def ia(meta):
    """Ilustración con Gemini. Sin caras de personas reales, sin texto, sin logos de marcas."""
    key = os.environ.get('GEMINI_API_KEY')
    if not key: return None
    prompt = (f"Editorial illustration for a gaming news site, 16:9, no text, no letters, no logos, no real people's faces "
              f"(use silhouettes, objects or scenery instead). Bold, modern, dark navy background (#06143f) with warm orange "
              f"(#ff6a3d) and yellow (#ffd23f) light accents. Topic: {meta['titulo']}. Context: {meta['resumen']}")
    r = HTTP.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent',
                  params={'key': key}, json={'contents': [{'parts': [{'text': prompt}]}],
                                             'generationConfig': {'responseModalities': ['IMAGE'], 'imageConfig': {'aspectRatio': '16:9'}}},
                  timeout=90)
    if r.status_code != 200: return None
    import base64
    for p in r.json().get('candidates', [{}])[0].get('content', {}).get('parts', []):
        if 'inlineData' in p:
            return base64.b64decode(p['inlineData']['data']), 'Ilustración generada para Corillo'
    return None


def _font(nombre, tam, peso):
    f = ImageFont.truetype(str(FONTS / nombre), tam)
    try: f.set_variation_by_axes([min(tam, 96), peso, 100] if nombre == 'bricolage.ttf' else [min(tam, 40), peso])
    except Exception: pass
    return f


def diseno(meta):
    """Portada de diseño: fondo Cobalto con el color de la categoría, la categoría y el título."""
    etiqueta, col = CATS.get(meta['cat'], CATS['corillo'])
    img = Image.new('RGB', (W, H), INK)
    luz = Image.new('RGB', (W, H), INK); g = ImageDraw.Draw(luz)
    g.ellipse((W - 760, -420, W + 360, 520), fill=tuple(int(c * .55) for c in col))
    g.ellipse((-420, H - 300, 520, H + 520), fill=(23, 51, 131))
    img = Image.blend(img, luz.filter(ImageFilter.GaussianBlur(170)), .95)
    d = ImageDraw.Draw(img)
    x, ancho = 110, W - 220
    f_cat = _font('dmsans.ttf', 34, 800)
    tw = d.textlength(etiqueta, font=f_cat)
    d.rounded_rectangle((x, 110, x + tw + 52, 170), radius=30, fill=tuple(int(c * .22 + i * .78) for c, i in zip(col, INK)))
    d.ellipse((x + 22, 133, x + 36, 147), fill=col)
    d.text((x + 46, 121), etiqueta, font=f_cat, fill=col)
    for tam in (112, 100, 88, 76, 66):  # el título más grande que quepa en 4 líneas
        f = _font('bricolage.ttf', tam, 800)
        palabras, lineas, cur = meta['titulo'].split(), [], ''
        for p in palabras:
            t = (cur + ' ' + p).strip()
            if d.textlength(t, font=f) <= ancho: cur = t
            else: lineas.append(cur); cur = p
        lineas.append(cur)
        if len(lineas) <= 4: break
    y = H - 110 - len(lineas) * int(tam * .98)
    for l in lineas[:4]:
        d.text((x, y), l, font=f, fill=BONE); y += int(tam * .98)
    logo = _font('bricolage.ttf', 34, 800)
    d.text((W - 110 - d.textlength('corillo.live', font=logo), 118), 'corillo.live', font=logo, fill=MUTE)
    buf = io.BytesIO(); img.save(buf, 'JPEG', quality=88); return buf.getvalue(), 'Portada de Corillo'


def a_16x9(jpeg):
    im = Image.open(io.BytesIO(jpeg)).convert('RGB')
    r = W / H
    if im.width / im.height > r:
        nw = int(im.height * r); im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
    else:
        nh = int(im.width / r); im = im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh))
    im = im.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=86, optimize=True); return buf.getvalue()


def portada(path, forzar=False, sin_ia=False, solo_diseno=False):
    texto, fm, meta = frontmatter(path)
    destino = SALIDA / f'{path.stem}.jpg'
    if 'image:' in fm and destino.exists() and not forzar:
        return 'ya tenía'
    # solo el juego que la nota declara (campo `game`, lo pone daily-news.py): las etiquetas no son juegos
    cands = [meta['juego']] if meta['juego'] else []
    res = None if solo_diseno else steam(cands)
    tipo = 'steam'
    if not res and not (sin_ia or solo_diseno):
        res, tipo = ia(meta), 'ia'
    if not res:
        res, tipo = diseno(meta), 'diseno'
    jpeg, credito = res
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(a_16x9(jpeg) if tipo != 'diseno' else jpeg)
    fm2 = re.sub(r'^(image|imageCredit):.*\n', '', fm, flags=re.M).rstrip('\n') + \
        f'\nimage: "/noticias/portadas/{path.stem}.jpg"\nimageCredit: {json.dumps(credito, ensure_ascii=False)}\n'
    path.write_text(texto.replace(fm, fm2, 1), encoding='utf-8', newline='\n')
    return f'{tipo}: {credito}'


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    notas = [Path(a) for a in args] or sorted(NOTAS.glob('20*.md'), reverse=True)[:9]
    for n in notas:
        print(f'{n.stem[:70]:70} → {portada(n, "--forzar" in sys.argv, "--sin-ia" in sys.argv, "--solo-diseno" in sys.argv)}')
