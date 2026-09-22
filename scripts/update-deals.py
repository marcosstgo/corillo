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
    for f in (HOME / '.env', Path('/home/corillo-adm/corillo-telegram/.env')):
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

# ───────────────────────── principal ─────────────────────────
def score(x): return x['pct'] + ((x.get('rating') or 75) - 75) + (25 if x.get('lowest') else 0)

LISTS = ('free', 'freeSteam', 'soon', 'steam', 'gog', 'humble', 'fanatical', 'gmg', 'gamersgate')

def canon(d):
    """Huella de lo que un visitante notaría (qué juegos, precios, descuentos, fechas). Ignora horas y conteos de reseñas, que cambian solos."""
    keep = ('id', 'price', 'original', 'pct', 'lowest', 'starts', 'ends', 'title', 'image')
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
            resp = CLIENT.post(hook, json={'username': 'Corillo Ofertas', 'embeds': [{
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

    for name in ('freeSteam', 'steam', 'gog', 'humble', 'fanatical', 'gmg', 'gamersgate'): fix_images(new[name], state)
    for name in LISTS: new[name] = drop_dead_links(new[name], state)
    if not a.dry_run: STATE.write_text(json.dumps(state))          # guarda la caché de imágenes/enlaces aunque no haya cambios

    if not (new['free'] or new['freeSteam'] or new['steam'] or new['gog']):
        log('sin datos en ninguna fuente: no se publica'); telegram('⚠️ Ofertas: ninguna tienda respondió. Se conserva lo anterior.'); sys.exit(1)
    out = {**new, 'updatedAt': now, 'asOf': asof}
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
    if len(errors) >= 3: telegram('⚠️ Ofertas: varias fuentes fallaron: ' + '; '.join(errors))

if __name__ == '__main__':
    main()
