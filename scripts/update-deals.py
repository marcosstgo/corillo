#!/home/corillo-adm/corillo-news/venv/bin/python
"""Ofertas de juegos de CORILLO (/ofertas/).

Consulta las tiendas (Epic, Steam, GOG) y CheapShark (mínimos históricos), valida, y escribe
/home/corillo-adm/corillo-deals/ofertas.json, que las páginas de Astro leen al compilar.
Si hay cambios reales, despliega (scripts/deploy-corillo.sh, con candado) y avisa al Discord de Corillo de los juegos GRATIS nuevos.

Reglas que no se rompen:
  - "Gratis" solo si el precio final es 0 (Epic lista descuentos dentro de la misma promoción; no son gratis).
  - Todo precio debe cuadrar con su descuento; lo que no cuadra se descarta.
  - Si una tienda falla, se conserva su última lista buena con su propia hora ("asOf"); nunca se publica una lista vacía.
  - Solo datos de las tiendas; nada se inventa.

Uso: update-deals.py [--dry-run] [--no-deploy]
"""
import argparse, datetime as dt, hashlib, html, json, os, re, subprocess, sys, time
from pathlib import Path
import httpx

REPO = Path('/var/www/stream')
HOME = Path('/home/corillo-adm/corillo-deals'); HOME.mkdir(parents=True, exist_ok=True)
DATA = HOME / 'ofertas.json'; STATE = HOME / 'state.json'; LOGF = HOME / 'update.log'
UA = 'CorilloDeals/1.0 (+https://corillo.live/ofertas/; hello@marcossantiago.com)'
CLIENT = httpx.Client(headers={'User-Agent': UA, 'Accept-Language': 'es-US,es;q=0.9'}, timeout=25, follow_redirects=True)

def log(*a):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} " + ' '.join(str(x) for x in a)
    print(line, flush=True)

def load_env():
    for f in (HOME / '.env', Path('/home/corillo-adm/corillo-telegram/.env'), Path('/home/corillo-adm/corillo-stoat/.env.discord')):
        if not f.exists(): continue
        for l in f.read_text().splitlines():
            if '=' in l and not l.lstrip().startswith('#'):
                k, v = l.split('=', 1); os.environ.setdefault(k.strip(), v.strip().strip('"\''))

def telegram(msg):
    try:
        CLIENT.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                    data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'text': msg, 'disable_web_page_preview': 'true'})
    except Exception as e: log('telegram falló:', e)

def get_json(url, tries=3, **kw):
    last = None
    for i in range(tries):
        try:
            r = CLIENT.get(url, **kw); r.raise_for_status(); return r.json()
        except Exception as e:
            last = e; time.sleep(2 * (i + 1))
    raise last

def get_text(url, tries=3, **kw):
    last = None
    for i in range(tries):
        try:
            r = CLIENT.get(url, **kw); r.raise_for_status(); return r.text
        except Exception as e:
            last = e; time.sleep(2 * (i + 1))
    raise last

def money(cents): return f"${cents / 100:,.2f}"

# ───────────────────────── Epic ─────────────────────────
def epic():
    j = get_json('https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=es-US&country=US')
    els = j['data']['Catalog']['searchStore']['elements']
    now, soon = [], []
    for e in els:
        title = (e.get('title') or '').strip()
        if not title or 'mystery' in title.lower(): continue           # los "juegos misteriosos" no tienen datos reales todavía
        slug = None
        for m in (e.get('offerMappings') or []) + ((e.get('catalogNs') or {}).get('mappings') or []):
            if m.get('pageSlug'): slug = m['pageSlug']; break
        slug = slug or e.get('productSlug') or e.get('urlSlug')
        if not slug or '/' in slug and slug.count('/') > 1: continue    # sin enlace fiable no se publica
        tp = (e.get('price') or {}).get('totalPrice') or {}
        orig, disc = tp.get('originalPrice'), tp.get('discountPrice')
        imgs = {i['type']: i['url'] for i in e.get('keyImages', []) if i.get('url', '').startswith('https://')}
        img = imgs.get('OfferImageWide') or imgs.get('DieselStoreFrontWide') or imgs.get('Thumbnail') or next(iter(imgs.values()), None)
        if img and 'cdn1.epicgames.com' in img and '?' not in img: img += '?h=540&resize=1&w=960&quality=medium'   # el original pesa ~1 MB
        base = {'id': 'epic:' + e['id'], 'title': title, 'store': 'epic', 'url': f'https://store.epicgames.com/es-ES/p/{slug}', 'image': img,
                'original': money(orig) if orig else None}
        pr = e.get('promotions') or {}
        cur = ((pr.get('promotionalOffers') or [{}])[0].get('promotionalOffers') or [None])[0]
        up = ((pr.get('upcomingPromotionalOffers') or [{}])[0].get('promotionalOffers') or [None])[0]
        if cur and cur.get('discountSetting', {}).get('discountPercentage') == 0 and disc == 0 and orig:
            now.append({**base, 'ends': cur['endDate'], 'starts': cur['startDate']})
        elif up and up.get('discountSetting', {}).get('discountPercentage') == 0 and orig:
            soon.append({**base, 'ends': up['endDate'], 'starts': up['startDate']})
        # (los descuentos parciales de Epic no se muestran aquí: no son gratis)
    now.sort(key=lambda x: x['ends']); soon.sort(key=lambda x: x['starts'])
    return now, soon

# ───────────────────────── Steam ─────────────────────────
def steam():
    out, seen = [], set()
    h = get_text('https://store.steampowered.com/search/results/', params={
        'query': '', 'start': 0, 'count': 100, 'specials': 1, 'cc': 'us', 'l': 'english', 'sort_by': 'Reviews_DESC', 'infinite': 1, 'force_infinite': 1})
    h = json.loads(h)['results_html']
    for row in re.split(r'(?=<a href="https://store\.steampowered\.com/app/)', h)[1:]:
        m = re.match(r'<a href="https://store\.steampowered\.com/app/(\d+)/', row)
        if not m or not re.search(r'data-ds-appid="%s"' % m.group(1), row): continue      # paquetes/DLC dobles: fuera
        appid = m.group(1)
        t = re.search(r'<span class="title">(.*?)</span>', row, re.S); d = re.search(r'data-discount="(\d+)"', row)
        pf = re.search(r'data-price-final="(\d+)"', row); po = re.search(r'discount_original_price">\s*\$?([\d,.]+)', row)
        if not (t and d and pf and po) or appid in seen: continue
        pct, final, orig = int(d.group(1)), int(pf.group(1)), float(po.group(1).replace(',', ''))
        if pct < 30 or final <= 0 or abs(final / 100 - orig * (1 - pct / 100)) > max(0.06, orig * 0.02): continue   # el precio debe cuadrar con el descuento
        tip = re.search(r'data-tooltip-html="([^"]*)"', row)
        rv = re.search(r'(\d+)\s*%\s*of the\s+([\d.,]+)', html.unescape(tip.group(1))) if tip else None
        rating, count = (int(rv.group(1)), int(re.sub(r'\D', '', rv.group(2)))) if rv else (None, 0)
        if rating is None or rating < 75 or count < 500: continue                               # solo juegos bien reseñados
        seen.add(appid)
        out.append({'id': 'steam:' + appid, 'appid': appid, 'title': html.unescape(t.group(1)).strip(), 'store': 'steam',
                    'url': f'https://store.steampowered.com/app/{appid}/', 'image': f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg',
                    'price': money(final), 'priceNum': final / 100, 'original': f'${orig:,.2f}', 'origNum': orig, 'pct': pct, 'rating': rating, 'reviews': count})
    return out


def steam_free():
    """Juegos de Steam a 100 % de descuento (gratis por tiempo limitado). Steam no da la fecha de fin en esta lista."""
    h = json.loads(get_text('https://store.steampowered.com/search/results/', params={
        'query': '', 'start': 0, 'count': 100, 'specials': 1, 'cc': 'us', 'l': 'english', 'category1': 998, 'sort_by': 'Price_ASC', 'infinite': 1, 'force_infinite': 1}))['results_html']
    out, seen = [], set()
    for row in re.split(r'(?=<a href="https://store\.steampowered\.com/app/)', h)[1:]:
        m = re.match(r'<a href="https://store\.steampowered\.com/app/(\d+)/', row)
        d = re.search(r'data-discount="(\d+)"', row); pf = re.search(r'data-price-final="(\d+)"', row)
        po = re.search(r'discount_original_price">\s*\$?([\d,.]+)', row); t = re.search(r'<span class="title">(.*?)</span>', row, re.S)
        if not (m and d and pf and po and t) or m.group(1) in seen: continue
        if int(d.group(1)) != 100 or int(pf.group(1)) != 0 or float(po.group(1).replace(',', '')) < 1: continue     # gratis solo con precio final 0 y precio original real
        seen.add(m.group(1)); appid = m.group(1)
        out.append({'id': 'steamfree:' + appid, 'title': html.unescape(t.group(1)).strip(), 'store': 'steam', 'url': f'https://store.steampowered.com/app/{appid}/',
                    'image': f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg', 'original': f'${float(po.group(1).replace(",", "")):,.2f}'})
    return out

# ───────────────────────── GOG ─────────────────────────
def gog():
    j = get_json('https://catalog.gog.com/v1/catalog', params={'limit': 100, 'order': 'desc:trending', 'discounted': 'eq:true',
        'productType': 'in:game,pack', 'countryCode': 'US', 'currencyCode': 'USD'})
    out = []
    for p in j.get('products', []):
        try:
            fin, base = float(p['price']['finalMoney']['amount']), float(p['price']['baseMoney']['amount'])
            pct = round((1 - fin / base) * 100)
            shown = int(re.sub(r'\D', '', p['price'].get('discount') or '0') or 0)
            cover = p.get('coverHorizontal') or ''
            mm = re.search(r'gog-statics\.com/([0-9a-f]{40,})', cover)
            if not (mm and p.get('storeLink', '').startswith('https://www.gog.com/')) or base <= 0 or fin <= 0: continue
            if pct < 30 or abs(pct - shown) > 1: continue                                       # el descuento mostrado debe coincidir con los precios
            rating = p.get('reviewsRating'); cnt = p.get('reviewsCount') or 0
            if rating is not None and (rating < 40 or cnt < 100): continue                      # escala GOG 0-50: 40 = 80 %
            out.append({'id': 'gog:' + str(p['id']), 'title': p['title'].strip(), 'store': 'gog', 'url': p['storeLink'],
                        'image': f'https://images.gog-statics.com/{mm.group(1)}_product_card_v2_mobile_slider_639.jpg',
                        'price': f'${fin:,.2f}', 'priceNum': fin, 'original': f'${base:,.2f}', 'origNum': base, 'pct': pct,
                        'rating': round(rating * 2) if rating else None, 'reviews': cnt})
        except (KeyError, ValueError, TypeError): continue
    return out


# ───────────────────── otras tiendas (CheapShark) ─────────────────────
EXTRA = {'11': ('humble', 'Humble Store'), '15': ('fanatical', 'Fanatical'), '3': ('gmg', 'Green Man Gaming'), '2': ('gamersgate', 'GamersGate')}

def cs_store(store_id, key):
    d = get_json('https://www.cheapshark.com/api/1.0/deals', params={'storeID': store_id, 'onSale': 1, 'pageSize': 60, 'sortBy': 'DealRating', 'upperPrice': 60})
    out, seen = [], set()
    for x in d:
        try:
            sale, normal, pct = float(x['salePrice']), float(x['normalPrice']), round(float(x['savings']))
            if sale <= 0 or normal <= 0 or pct < 30 or abs((1 - sale / normal) * 100 - pct) > 1.5: continue      # el precio debe cuadrar con el descuento
            sr, sc, mc = int(x.get('steamRatingPercent') or 0), int(x.get('steamRatingCount') or 0), int(x.get('metacriticScore') or 0)
            if not ((sr >= 75 and sc >= 500) or mc >= 75): continue                                       # solo juegos bien valorados
            if x['gameID'] in seen or not x.get('dealID'): continue
            img = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{x['steamAppID']}/header.jpg" if x.get('steamAppID') else x.get('thumb')
            if not img: continue
            seen.add(x['gameID'])
            out.append({'id': f"{key}:{x['gameID']}", 'gameID': x['gameID'], 'title': html.unescape(x['title']).strip(), 'store': key,
                        'url': 'https://www.cheapshark.com/redirect?dealID=' + x['dealID'], 'image': img,
                        'price': f'${sale:,.2f}', 'priceNum': sale, 'original': f'${normal:,.2f}', 'origNum': normal, 'pct': pct,
                        'rating': sr if sr >= 1 and sc >= 100 else None, 'reviews': sc if sr and sc >= 100 else 0})
        except (KeyError, ValueError, TypeError): continue
    return out

# ───────────────────── mínimos históricos (CheapShark) ─────────────────────
def lowest(items):
    """Marca 'lowest' cuando el precio actual iguala el mínimo histórico que reporta CheapShark. Si falla, no se marca nada."""
    try:
        by_app = {}
        if any('appid' in it for it in items):
            deals = get_json('https://www.cheapshark.com/api/1.0/deals', params={'storeID': 1, 'onSale': 1, 'pageSize': 60, 'sortBy': 'DealRating'})
            by_app = {d['steamAppID']: d['gameID'] for d in deals if d.get('steamAppID')}
        pairs = [(it, it.get('gameID') or by_app.get(it.get('appid'))) for it in items]
        pairs = [(it, g) for it, g in pairs if g]
        for i in range(0, len(pairs), 25):
            chunk = pairs[i:i + 25]
            res = get_json('https://www.cheapshark.com/api/1.0/games', params={'ids': ','.join(sorted({g for _, g in chunk}))})
            for it, g in chunk:
                ce = (res.get(g) or {}).get('cheapestPriceEver', {}).get('price')
                if ce is not None and it['priceNum'] <= float(ce) + 0.005: it['lowest'] = True
    except Exception as e:
        log('CheapShark no respondió (sin marcas de mínimo histórico):', type(e).__name__)

# ───────────────────── enlaces: solo se publican ofertas cuyo enlace funciona ─────────────────────
def link_ok(url, state):
    """Solo descarta por señales claras de enlace muerto (404/410). Un bloqueo o límite de tasa (403/429/5xx,
    o la conexión falla) no prueba que la oferta no exista: se deja pasar para no descartar ofertas buenas."""
    cache = state.setdefault('link', {})
    if url in cache: return cache[url]
    try:
        r = CLIENT.head(url, timeout=10, follow_redirects=True)
        if r.status_code in (405, 501): r = CLIENT.get(url, timeout=10, follow_redirects=True)  # algunas tiendas no permiten HEAD
        ok = r.status_code not in (404, 410)
    except Exception: return True
    cache[url] = ok
    if len(cache) > 4000: [cache.pop(k) for k in list(cache)[:1000]]
    return ok

def drop_dead_links(items, state):
    keep = []
    for it in items:
        if link_ok(it['url'], state): keep.append(it)
        time.sleep(0.1)                             # no golpear las tiendas/CheapShark demasiado rápido
    dropped = len(items) - len(keep)
    if dropped: log(f'  {dropped} oferta(s) con enlace muerto (404/410): descartada(s)')
    return keep

# ───────────────────── imágenes: solo se publican las que existen ─────────────────────
def img_ok(url, state):
    cache = state.setdefault('img', {})
    if url in cache: return cache[url]
    try:
        r = CLIENT.head(url, timeout=10); ok = r.status_code == 200 and 'image' in r.headers.get('content-type', '')
    except Exception: return True                  # si no se pudo comprobar (red), se deja como está y no se guarda
    cache[url] = ok
    if len(cache) > 4000: [cache.pop(k) for k in list(cache)[:1000]]
    return ok

def fix_images(items, state):
    """Steam tiene juegos cuya portada vive en otra ruta: se prueba la clásica y, si ninguna existe, la tarjeta sale sin imagen (nunca rota)."""
    for it in items:
        u = it.get('image')
        if not u or 'cdn1.epicgames.com' in u or img_ok(u, state): continue
        m = re.search(r'steam/apps/(\d+)/', u)
        alts = [f'https://cdn.cloudflare.steamstatic.com/steam/apps/{m.group(1)}/header.jpg', f'https://cdn.akamai.steamstatic.com/steam/apps/{m.group(1)}/header.jpg'] if m else []
        it['image'] = next((a for a in alts if img_ok(a, state)), None)

# ───────────────────── equipo y consolas (dealnews) ─────────────────────
# dealnews es una web de ofertas curada por editores: cada oferta trae tienda, precio y fecha de vencimiento ya separados.
# Reddit (r/buildapcsales) y Slickdeals bloquean las consultas desde este servidor; por eso esta fuente.
DN = 'https://www.dealnews.com'
DN_UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) ' + UA}
DN_NS = {'dn': 'https://www.dealnews.com/ns/rss/1.0.htm', 'media': 'http://search.yahoo.com/mrss/'}
# lista -> categoría -> (ruta del feed, filtro: el título debe parecer de gaming; None = todo vale)
DN_CATS = {
    'equipo': {
        'monitores': ('/c75/Computers/Peripherals/Monitors/', r'gaming|\b1[2-9]\dhz|\b[2-9]\d\dhz|\boled\b|ultragear|odyssey|predator|\brog\b|alienware|aorus|\bmsi\b|nitro|\btuf\b'),
        'graficas': ('/c113/Computers/Upgrades-Components/Video-Cards/', r'rtx|radeon|\brx ?\d|geforce|\barc\b'),
        'laptops': ('/c49/Computers/Laptops/f31/Gaming/', r'gaming|rtx|radeon|legion|\brog\b|\btuf\b|omen|victus|nitro|predator|alienware|katana|\bloq\b'),
        'audio': ('/c155/Electronics/Audio-Components/Headphones/', r'gaming|headset|hyperx|steelseries|razer|astro|turtle beach|logitech g|corsair|arctis|kraken|pulse'),
        'perifericos': ('/c70/Computers/Peripherals/Input-Devices/', r'gaming|mechanical|controller|gamepad|razer|steelseries|logitech g\b|logitech g[0-9 ]|hyperx|corsair|8bitdo|dualsense|xbox|wooting|keychron'),
    },
    'consola': {
        'ps5': ('/c191/Gaming-Toys/Video-Games/f1915/Play-Station-5/', None),
        'xbox': ('/c191/Gaming-Toys/Video-Games/f1918/Xbox-Series-S-X/', None),
        'switch': ('/c191/Gaming-Toys/Video-Games/f1652/Nintendo-Switch/', None),
    },
}
DN_LABEL = {'monitores': 'Monitor', 'graficas': 'Tarjeta gráfica', 'laptops': 'Laptop gamer', 'audio': 'Audífonos',
            'perifericos': 'Teclado, ratón o control', 'ps5': 'PlayStation', 'xbox': 'Xbox', 'switch': 'Nintendo'}
# Solo tiendas que envían a Puerto Rico (o venden en digital). Best Buy, Target, Walmart.com y Woot no envían a PR.
# Newegg, Dell, Lenovo, HP y eBay envían a PR en la mayoría de los productos, pero no en todos: la página lo advierte.
PR_OK = {'Amazon', 'Newegg', 'eBay', 'B&H Photo Video', 'Dell Technologies', 'Lenovo', 'HP',
         'PlayStation Store', 'Xbox Store', 'Microsoft Store', 'Nintendo', 'Steam'}
DN_JUNK = r'screen protector|replacement|radiator|cooler for|bracket|riser|cable|adapter|\bskin\b|decal|charging (?:dock|station|stand)|carrying case|thumb grips'   # accesorios sueltos: no son "equipo"
ARCHIVE_DAYS = 30                      # una oferta compartida sigue abriendo (como "terminada") este tiempo

def slugify(t):
    t = html.unescape(t).lower()
    t = re.sub(r'[áàä]', 'a', t); t = re.sub(r'[éèë]', 'e', t); t = re.sub(r'[íìï]', 'i', t); t = re.sub(r'[óòö]', 'o', t); t = re.sub(r'[úùü]', 'u', t); t = t.replace('ñ', 'n')
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')[:70].rstrip('-')

def dealnews(lista):
    import xml.etree.ElementTree as ET
    out, seen = [], set()
    for cat, (path, rx) in DN_CATS[lista].items():
        r = CLIENT.get(DN + path, params={'rss': 1}, headers=DN_UA); r.raise_for_status()
        root = ET.fromstring(r.content)
        for it in root.iter('item'):
            title = html.unescape(it.findtext('title') or '').strip()
            retailer = html.unescape(it.findtext('dn:retailer', '', DN_NS)).strip()
            kind = it.findtext('dn:dealType', '', DN_NS)
            pe = it.find('dn:price', DN_NS)
            m = re.match(r'(.+?) for \$([\d,]+(?:\.\d\d)?)(.*)$', title)
            gid = re.search(r'/(\d+)\.html', it.findtext('guid') or '')
            if kind == 'sale' or not m or pe is None or not gid or retailer not in PR_OK: continue   # solo productos concretos con precio
            name, extra = m.group(1).strip(), m.group(3)
            if re.search(r'\b(up to|from|deals at|sale|coupon)\b', name, re.I): continue
            if rx and not re.search(rx, name, re.I): continue
            if re.search(DN_JUNK, name, re.I): continue
            try: price = float(pe.text)
            except (TypeError, ValueError): continue
            if price <= 0 or abs(price - float(m.group(2).replace(',', ''))) > 0.01: continue        # el precio del título debe cuadrar con el del dato
            did = 'dn:' + gid.group(1)
            if did in seen: continue
            seen.add(did)
            desc = html.unescape(it.findtext('description') or '')
            summary = re.sub(r'<[^>]+>', ' ', (re.search(r'class="snippet summary" title="([^"]*)"', desc) or re.search(r'(.*)', '')).group(1))
            save = re.search(r'\$([\d,]+(?:\.\d\d)?) (?:off|under)', summary)
            img = (it.find('media:content', DN_NS).attrib.get('url') if it.find('media:content', DN_NS) is not None else None)
            if img: img = re.sub(r'\?.*$', '', img) + '?h=600&w=600'
            link = re.sub(r'\?.*$', '', it.findtext('link') or '')
            if not link.startswith(DN + '/'): continue
            out.append({'id': did, 'slug': f"{slugify(name)}-{gid.group(1)}", 'title': name, 'cat': cat, 'catLabel': DN_LABEL[cat], 'list': lista,
                        'retailer': retailer, 'url': link, 'image': img, 'price': f'${price:,.2f}'.replace('.00', ''), 'priceNum': price,
                        'save': f"${save.group(1)}" if save else None, 'prime': 'w/ Prime' in extra, 'freeShip': 'free shipping' in extra.lower(),
                        'staff': it.findtext('dn:staffPick', '', DN_NS) == 'true', 'expires': it.findtext('dn:expires', '', DN_NS) or None,
                        'posted': dt.datetime.strptime(it.findtext('pubDate'), '%a, %d %b %Y %H:%M:%S %z').astimezone(dt.timezone.utc).isoformat(timespec='seconds'),
                        'summary': summary.strip()[:300] or None})
        time.sleep(1)                                                     # amable con dealnews: un feed por segundo
    now = dt.datetime.now(dt.timezone.utc)
    fresh = (now - dt.timedelta(days=10)).isoformat(timespec='seconds')        # dealnews a veces re-lista ofertas viejas: solo las de los últimos 10 días
    out = [x for x in out if x['posted'] >= fresh and (not x['expires'] or x['expires'] > now.isoformat(timespec='seconds'))]
    out.sort(key=lambda x: x['posted'], reverse=True)
    uniq, names = [], set()
    for x in out:                                                               # el mismo producto en dos categorías o dos veces: una sola
        k = re.sub(r'[^a-z0-9]+', '', x['title'].lower().replace('-inch', '').replace('"', ''))
        k2 = (x['retailer'], x['priceNum'], x['cat'])
        if k in names or k2 in names: continue
        names.update((k, k2)); uniq.append(x)
    return uniq[:60]

def og_cards(items, state):
    """Genera la tarjeta para compartir de cada oferta nueva (una sola vez por oferta)."""
    import deals_og
    made = set(state.get('og', []))
    for it in items:
        dest = REPO / 'public' / 'ofertas' / 'og' / f"{it['slug']}.png"
        if it['id'] in made and dest.exists(): continue
        pic = None
        if it.get('image'):
            try:
                r = CLIENT.get(it['image'], headers=DN_UA, timeout=15)
                if r.status_code == 200 and r.headers.get('content-type', '').startswith('image'): pic = r.content
            except Exception: pass
        try: deals_og.card(it, pic, dest, it['catLabel']); made.add(it['id'])
        except Exception as e: log('tarjeta OG falló', it['slug'], type(e).__name__, e)
    state['og'] = sorted(made)[-3000:]

def prune_og(keep_slugs):
    """Borra las tarjetas de ofertas que ya salieron del archivo."""
    d = REPO / 'public' / 'ofertas' / 'og'
    if not d.exists(): return
    for f in d.glob('*.png'):
        if f.stem not in keep_slugs: f.unlink(missing_ok=True)

def update_archive(prev, live):
    """Ofertas que salieron de la lista: su página sigue existiendo (como terminada) ARCHIVE_DAYS días, para que un enlace compartido no dé 404."""
    now = dt.datetime.now(dt.timezone.utc)
    live_ids = {x['id'] for x in live}
    gone = [dict(x, endedAt=now.isoformat(timespec='seconds')) for x in prev.get('equipo', []) + prev.get('consola', []) if x['id'] not in live_ids]
    arch = {x['id']: x for x in prev.get('archivo', []) + gone if x['id'] not in live_ids}
    keep = [x for x in arch.values() if dt.datetime.fromisoformat(x['endedAt']) > now - dt.timedelta(days=ARCHIVE_DAYS)]
    return sorted(keep, key=lambda x: x['endedAt'], reverse=True)

# ───────────────────── avisos de equipo y consolas en Discord (Corillo-Bot, con botones) ─────────────────────
DISCORD_API = 'https://discord.com/api/v10'
DAILY_MAX = {'equipo': 5, 'consola': 3}          # para que el canal no se vuelva spam
RUN_MAX = 2                                       # por corrida (cada hora)

def share_links(it):
    from urllib.parse import quote
    page = f"https://corillo.live/ofertas/o/{it['slug']}/"
    msg = f"{it['title']} a {it['price']} en {it['retailer']}"
    return page, {'whatsapp': f"https://wa.me/?text={quote(msg + ' ' + page)}",
                  'telegram': f"https://t.me/share/url?url={quote(page)}&text={quote(msg)}"}

def discord_hardware(items, state):
    token, roles_raw = os.environ.get('DISCORD_BOT_TOKEN'), os.environ.get('DISCORD_DEALS_ROLES', '')
    chans = {'equipo': os.environ.get('DISCORD_CH_OFERTAS_EQUIPO'), 'consola': os.environ.get('DISCORD_CH_OFERTAS')}
    if not token: return
    roles = dict(x.split(':', 1) for x in roles_raw.split(',') if ':' in x)      # cat:role_id
    sent = state.setdefault('hw_notified', {})                                     # id -> fecha de aviso (ISO)
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).date().isoformat()
    if not state.get('hw_seeded'):                                                 # primera vez: no se inunda el canal con todo lo vigente
        for it in items[2:]: sent[it['id']] = 'seed'
        state['hw_seeded'] = True
    count = {l: sum(1 for v in sent.values() if v == today + ':' + l) for l in DAILY_MAX}
    run = 0
    ordered = sorted(items, key=lambda x: x['posted'], reverse=True)
    for it in sorted(ordered, key=lambda x: not x['staff']):             # primero las recomendadas, y dentro de cada grupo la más nueva
        if it['id'] in sent or run >= RUN_MAX: continue
        l = it['list']
        if not chans.get(l) or count[l] >= DAILY_MAX[l]: continue
        page, sh = share_links(it)
        bits = [f"**{it['price']}** en {it['retailer']}"]
        if it.get('save'): bits.append(f"Ahorras {it['save']}")
        if it.get('prime'): bits.append('con Prime')
        if it.get('freeShip'): bits.append('envío gratis')
        role = roles.get(it['cat'])
        body = {'content': f"<@&{role}>" if role else '', 'allowed_mentions': {'roles': [role] if role else []},
                'embeds': [{'title': it['title'][:250], 'url': page, 'color': 0xFF6A3D if l == 'equipo' else 0xFFD23F,
                            'description': ' · '.join(bits) + ('\n⭐ Recomendada por los editores de dealnews' if it.get('staff') else ''),
                            'author': {'name': it['catLabel']},
                            'image': {'url': f"https://corillo.live/ofertas/og/{it['slug']}.png"},
                            'footer': {'text': 'Precio de EE. UU., la tienda envía a PR. Confirma el precio final antes de comprar.'}}],
                'components': [{'type': 1, 'components': [
                    {'type': 2, 'style': 5, 'label': 'Ver oferta', 'url': page},
                    {'type': 2, 'style': 5, 'label': 'WhatsApp', 'url': sh['whatsapp']},
                    {'type': 2, 'style': 5, 'label': 'Telegram', 'url': sh['telegram']}]}]}
        try:
            r = CLIENT.post(f"{DISCORD_API}/channels/{chans[l]}/messages", json=body, headers={'Authorization': 'Bot ' + token}, timeout=15)
            r.raise_for_status()
            sent[it['id']] = today + ':' + l; count[l] += 1; run += 1
            log('Discord (bot): avisado', it['title'][:60])
        except Exception as e: log('Discord (bot) falló:', type(e).__name__, str(e)[:160])
    if len(sent) > 2000:
        for k in list(sent)[:500]: sent.pop(k)

# ───────────────────── grupo de WhatsApp (vía OpenClaw, que está vinculado al WhatsApp de Marcos) ─────────────────────
WA_DAILY_MAX = 3                                  # el grupo es de amigos: pocas y buenas

def whatsapp_group(items, state):
    """Publica en el grupo las ofertas que acaban de salir en Discord. Apagado si WHATSAPP_DEALS_GROUP no está en ~/corillo-deals/.env."""
    group = os.environ.get('WHATSAPP_DEALS_GROUP')
    if not group: return
    sent = state.setdefault('wa_sent', {})
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).date().isoformat()
    n_today = sum(1 for v in sent.values() if v == today)
    disc = state.get('hw_notified', {})
    fresh = [it for it in items if it['id'] not in sent and str(disc.get(it['id'], '')).startswith(today)]   # solo lo que hoy salió en Discord
    for it in fresh:
        if n_today >= WA_DAILY_MAX: break
        page, _ = share_links(it)
        lines = [f"*{it['title']}*", f"{it['price']} en {it['retailer']}" + (f" · ahorras {it['save']}" if it.get('save') else '') + (' · con Prime' if it.get('prime') else ''), page]
        cmd = ['/usr/bin/openclaw', 'message', 'send', '--channel', 'whatsapp', '--target', group, '--message', '\n'.join(lines), '--json']
        og = REPO / 'public' / 'ofertas' / 'og' / f"{it['slug']}.png"
        if og.exists(): cmd += ['--media', str(og)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if r.returncode != 0: raise RuntimeError((r.stdout + r.stderr)[-200:])
            sent[it['id']] = today; n_today += 1
            log('WhatsApp: publicado', it['title'][:60])
        except Exception as e:
            log('WhatsApp falló:', str(e)[:200]); break                     # si OpenClaw o WhatsApp están caídos, se reintenta la próxima hora
    for k in [k for k, v in sent.items() if v < (dt.date.today() - dt.timedelta(days=30)).isoformat()]: sent.pop(k)

# ───────────────────────── principal ─────────────────────────
def score(x): return x['pct'] + ((x.get('rating') or 75) - 75) + (25 if x.get('lowest') else 0)

LISTS = ('free', 'freeSteam', 'soon', 'steam', 'gog', 'humble', 'fanatical', 'gmg', 'gamersgate', 'equipo', 'consola')

def canon(d):
    """Huella de lo que un visitante notaría (qué juegos, precios, descuentos, fechas). Ignora horas y conteos de reseñas, que cambian solos."""
    keep = ('id', 'price', 'original', 'pct', 'lowest', 'starts', 'ends', 'title', 'image', 'expires')
    proj = {k: [{f: x.get(f) for f in keep} for x in d.get(k, [])] for k in LISTS}
    return hashlib.md5(json.dumps(proj, sort_keys=True).encode()).hexdigest()

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
def discord_new_free(free, state):
    hook = os.environ.get('DISCORD_DEALS_WEBHOOK')
    if not hook: return 0                      # sin webhook no se marca nada como avisado: cuando se configure, saldrán los que estén vigentes
    sent = set(state.get('notified', []))
    fresh = [g for g in free if g['id'] not in sent]
    for g in fresh:
        try:
            label = 'Epic' if g['store'] == 'epic' else 'Steam'
            if g.get('ends'):
                end = dt.datetime.fromisoformat(g['ends'].replace('Z', '+00:00')).astimezone(dt.timezone(dt.timedelta(hours=-4)))
                when = f"Gratis hasta el {end.day} de {MESES[end.month - 1]}."
            else: when = 'Gratis por tiempo limitado: reclámalo cuanto antes.'
            role = os.environ.get('DISCORD_ROLE_GRATIS')                    # quien escogió 🔔 Juegos gratis recibe la mención
            resp = CLIENT.post(hook, json={'username': 'Corillo Ofertas', 'content': f'<@&{role}>' if role else '',
                                           'allowed_mentions': {'roles': [role] if role else []}, 'embeds': [{
                'title': f"Gratis ahora en {label}: {g['title']}", 'url': g['url'], 'color': 0xFFD23F,
                'description': f"Normalmente {g['original']}. {when}\nMás ofertas: https://corillo.live/ofertas/gratis/",
                'image': {'url': g['image']} if g.get('image') else {}}]}, timeout=15)
            resp.raise_for_status()               # solo cuenta como avisado si Discord lo aceptó
            log('Discord: avisado', g['title'])
        except Exception as e: log('Discord falló:', e); continue
        sent.add(g['id'])
    state['notified'] = sorted(sent)[-80:]
    return len(fresh)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--no-deploy', action='store_true'); a = ap.parse_args()
    load_env()
    try: prev = json.loads(DATA.read_text())
    except Exception: prev = {}
    try: state = json.loads(STATE.read_text())
    except Exception: state = {}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    new = {k: prev.get(k, []) for k in LISTS}; asof = dict(prev.get('asOf', {})); errors = []

    def attempt(name, fn):
        try:
            r = fn(); asof[name] = now; return r
        except Exception as e:
            errors.append(f'{name}: {type(e).__name__}: {str(e)[:120]}'); log(f'{name} FALLÓ (se conserva la lista anterior):', errors[-1]); return None

    r = attempt('epic', epic)
    if r is not None:
        # "próximamente" es estable: Epic a veces omite un juego anunciado en una respuesta y lo trae en la siguiente. Se conserva 6 h si su fecha no ha llegado.
        seen = state.setdefault('soon_seen', {}); t = time.time(); merged = {x['id']: x for x in r[1]}
        for x in r[1]: seen[x['id']] = t
        for x in prev.get('soon', []):
            if x['id'] not in merged and t - seen.get(x['id'], 0) < 6 * 3600 and x['starts'] > now: merged[x['id']] = x
        new['free'], new['soon'] = r[0], sorted(merged.values(), key=lambda x: x['starts'])
        log(f"epic: {len(r[0])} gratis ahora, {len(new['soon'])} próximos")
    r = attempt('steamfree', steam_free)
    if r is not None: new['freeSteam'] = r; log(f'steam gratis (100 % off): {len(r)}')

    priced = []                                                            # listas con precio: se ordenan y se marcan los mínimos históricos juntas
    for name, fn, keep in (('steam', steam, 48), ('gog', gog, 24)) + tuple((k, (lambda sid=sid, k=k: cs_store(sid, k)), 24) for sid, (k, _) in EXTRA.items()):
        r = attempt(name, fn)
        if r is None: continue
        if not r: errors.append(f'{name}: lista vacía'); log(f'{name}: lista vacía (se conserva la anterior)'); continue
        r.sort(key=lambda x: (-score(x), x['id'])); new[name] = r; priced.append((name, keep)); log(f'{name}: {len(r)} válidas')
    lowest([it for name, _ in priced for it in new[name] if name != 'gog'])
    for name, keep in priced:
        new[name].sort(key=lambda x: (-score(x), x['id'])); new[name] = new[name][:keep]

    for name in ('equipo', 'consola'):                                     # equipo y juegos de consola (dealnews)
        r = attempt(name, lambda name=name: dealnews(name))
        if r is None: continue
        if not r: errors.append(f'{name}: lista vacía'); log(f'{name}: lista vacía (se conserva la anterior)'); continue
        new[name] = r; log(f'{name}: {len(r)} válidas')

    for name in ('freeSteam', 'steam', 'gog', 'humble', 'fanatical', 'gmg', 'gamersgate'): fix_images(new[name], state)
    for name in LISTS: new[name] = drop_dead_links(new[name], state)
    if not a.dry_run: STATE.write_text(json.dumps(state))          # guarda la caché de imágenes/enlaces aunque no haya cambios

    if not (new['free'] or new['freeSteam'] or new['steam'] or new['gog']):
        log('sin datos en ninguna fuente: no se publica'); telegram('⚠️ Ofertas: ninguna tienda respondió. Se conserva lo anterior.'); sys.exit(1)
    hw = new['equipo'] + new['consola']
    archivo = update_archive(prev, hw)
    if not a.dry_run:
        og_cards(hw + archivo, state); prune_og({x['slug'] for x in hw + archivo})
    out = {**new, 'archivo': archivo, 'updatedAt': now, 'asOf': asof}
    changed = canon(out) != canon(prev)
    log('cambios:', 'sí' if changed else 'no', '|', ' '.join(f'{k}={len(out[k])}' for k in LISTS))
    if a.dry_run:
        print(json.dumps({k: [(x['title'], x.get('price') or 'GRATIS', x.get('pct'), x.get('rating'), x.get('lowest')) for x in out[k][:4]] for k in LISTS}, ensure_ascii=False, indent=1)[:2600]); return
    if changed or 'updatedAt' not in prev:
        tmp = DATA.with_suffix('.tmp'); tmp.write_text(json.dumps(out, ensure_ascii=False)); tmp.replace(DATA)
        discord_new_free(out['free'] + out['freeSteam'], state); STATE.write_text(json.dumps(state))
        if not a.no_deploy:
            r = subprocess.run(['bash', 'scripts/deploy-corillo.sh'], cwd=REPO, text=True, capture_output=True)
            log('deploy', 'OK' if r.returncode == 0 else 'FALLÓ')
            if r.returncode: telegram('❌ Ofertas: el build falló con los datos nuevos (el sitio sigue como estaba).\n' + (r.stdout + r.stderr)[-400:]); sys.exit(1)
    if not a.no_deploy:                                                  # los avisos enlazan a páginas del sitio: solo después de un deploy bueno
        discord_hardware(out['equipo'] + out['consola'], state); STATE.write_text(json.dumps(state))
        whatsapp_group(out['equipo'] + out['consola'], state); STATE.write_text(json.dumps(state))
    if len(errors) >= 3: telegram('⚠️ Ofertas: varias fuentes fallaron: ' + '; '.join(errors))

if __name__ == '__main__':
    main()
