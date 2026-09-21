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

# ───────────────────── mínimos históricos (CheapShark) ─────────────────────
def lowest(steam_items):
    """Marca 'lowest' cuando el precio actual iguala el mínimo histórico que reporta CheapShark. Si falla, no se marca nada."""
    try:
        deals = get_json('https://www.cheapshark.com/api/1.0/deals', params={'storeID': 1, 'onSale': 1, 'pageSize': 60, 'sortBy': 'DealRating'})
        by_app = {d['steamAppID']: d['gameID'] for d in deals if d.get('steamAppID')}
        ids = [(it, by_app[it['appid']]) for it in steam_items if it['appid'] in by_app]
        for i in range(0, len(ids), 25):
            chunk = ids[i:i + 25]
            res = get_json('https://www.cheapshark.com/api/1.0/games', params={'ids': ','.join(g for _, g in chunk)})
            for it, g in chunk:
                ce = (res.get(g) or {}).get('cheapestPriceEver', {}).get('price')
                if ce is not None and it['priceNum'] <= float(ce) + 0.005: it['lowest'] = True
    except Exception as e:
        log('CheapShark no respondió (sin marcas de mínimo histórico):', type(e).__name__)

# ───────────────────────── principal ─────────────────────────
def score(x): return x['pct'] + ((x.get('rating') or 75) - 75) + (25 if x.get('lowest') else 0)

def canon(d):
    """Huella de lo que un visitante notaría (qué juegos, precios, descuentos, fechas). Ignora horas y conteos de reseñas, que cambian solos."""
    keep = ('id', 'price', 'original', 'pct', 'lowest', 'starts', 'ends', 'title')
    proj = {k: [{f: x.get(f) for f in keep} for x in d.get(k, [])] for k in ('free', 'soon', 'steam', 'gog')}
    return hashlib.md5(json.dumps(proj, sort_keys=True).encode()).hexdigest()

def discord_new_free(free, state):
    hook = os.environ.get('DISCORD_DEALS_WEBHOOK')
    sent = set(state.get('notified', []))
    fresh = [g for g in free if g['id'] not in sent]
    for g in fresh:
        if hook:
            try:
                end = dt.datetime.fromisoformat(g['ends'].replace('Z', '+00:00')).astimezone(dt.timezone(dt.timedelta(hours=-4)))
                CLIENT.post(hook, json={'username': 'Corillo Ofertas', 'embeds': [{
                    'title': f"Gratis ahora en Epic: {g['title']}", 'url': g['url'], 'color': 0xFFD23F,
                    'description': f"Normalmente {g['original']}. Gratis hasta el {end.day} de {['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'][end.month-1]}.\nMás ofertas: https://corillo.live/ofertas/",
                    'image': {'url': g['image']} if g.get('image') else {}}]}, timeout=15)
                log('Discord: avisado', g['title'])
            except Exception as e: log('Discord falló:', e); continue
        sent.add(g['id'])
    state['notified'] = sorted(sent)[-60:]
    return len(fresh)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--no-deploy', action='store_true'); a = ap.parse_args()
    load_env()
    try: prev = json.loads(DATA.read_text())
    except Exception: prev = {'free': [], 'soon': [], 'steam': [], 'gog': [], 'asOf': {}}
    try: state = json.loads(STATE.read_text())
    except Exception: state = {}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    new = {k: prev.get(k, []) for k in ('free', 'soon', 'steam', 'gog')}; asof = dict(prev.get('asOf', {})); errors = []

    for name, fn in (('epic', epic), ('steam', steam), ('gog', gog)):
        try:
            r = fn()
            if name == 'epic':
                new['free'], new['soon'] = r; log(f'epic: {len(r[0])} gratis ahora, {len(r[1])} próximos')
            else:
                if not r: raise ValueError('lista vacía')
                if name == 'steam': lowest(r)
                r.sort(key=lambda x: (-score(x), x['id'])); new[name] = r[:24 if name == 'steam' else 12]; log(f'{name}: {len(r)} válidas → {len(new[name])}')
            asof[name] = now
        except Exception as e:
            errors.append(f'{name}: {type(e).__name__}: {str(e)[:120]}'); log(f'{name} FALLÓ (se conserva la lista anterior):', errors[-1])

    if not (new['free'] or new['steam'] or new['gog']):
        log('sin datos en ninguna fuente: no se publica'); telegram('⚠️ Ofertas: ninguna tienda respondió. Se conserva lo anterior.'); sys.exit(1)
    out = {**new, 'updatedAt': now, 'asOf': asof}
    changed = canon(out) != canon(prev)
    log(f"cambios: {'sí' if changed else 'no'} | gratis {len(out['free'])} | steam {len(out['steam'])} | gog {len(out['gog'])}")
    if a.dry_run:
        print(json.dumps({k: [(x['title'], x.get('price') or 'GRATIS', x.get('pct'), x.get('rating'), x.get('lowest')) for x in v] if isinstance(v, list) else v for k, v in out.items()}, ensure_ascii=False, indent=1)[:3500]); return
    if changed or 'updatedAt' not in prev:
        tmp = DATA.with_suffix('.tmp'); tmp.write_text(json.dumps(out, ensure_ascii=False)); tmp.replace(DATA)
        n = discord_new_free(out['free'], state); STATE.write_text(json.dumps(state))
        if not a.no_deploy:
            r = subprocess.run(['bash', 'scripts/deploy-corillo.sh'], cwd=REPO, text=True, capture_output=True)
            log('deploy', 'OK' if r.returncode == 0 else 'FALLÓ')
            if r.returncode: telegram('❌ Ofertas: el build falló con los datos nuevos (el sitio sigue como estaba).\n' + (r.stdout + r.stderr)[-400:]); sys.exit(1)
    elif errors:
        pass
    if errors and len(errors) >= 2: telegram('⚠️ Ofertas: varias tiendas fallaron: ' + '; '.join(errors))

if __name__ == '__main__':
    main()
