"""Tarjetas para compartir (1200x630) de las ofertas de equipo y consolas.

Las genera scripts/update-deals.py en public/ofertas/og/<slug>.png: son la vista previa que sale en
WhatsApp, Telegram, X y Discord cuando alguien comparte la página de una oferta.
"""
import io, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path.home() / 'corillo-deals' / 'fonts'
W, H = 1200, 630
INK, BONE, MUTE, MAG, ORANGE = (6, 20, 63), (245, 248, 255), (164, 182, 230), (255, 210, 63), (255, 106, 61)


def _font(name, size, weight):
    f = ImageFont.truetype(str(FONTS / name), size)
    try: f.set_variation_by_axes([size, weight] if name == 'bricolage.ttf' else [weight])
    except Exception: pass
    return f


def _fit_lines(draw, text, font, width, max_lines):
    """Parte el título en líneas que caben en `width`; corta con … si no cabe en max_lines."""
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= width: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while draw.textlength(lines[-1] + '…', font=font) > width and ' ' in lines[-1]: lines[-1] = lines[-1].rsplit(' ', 1)[0]
        lines[-1] += '…'
    return lines


def card(deal, product_jpeg, out_path, cat_label):
    """deal: dict con title, price, retailer, save (opcional). product_jpeg: bytes de la imagen o None."""
    img = Image.new('RGB', (W, H), INK)
    # resplandor de fondo con los colores del sitio
    glow = Image.new('RGB', (W, H), INK); g = ImageDraw.Draw(glow)
    g.ellipse((700, -260, 1400, 380), fill=(70, 40, 20)); g.ellipse((-200, 380, 500, 900), fill=(20, 50, 110))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(120)), 0.9)
    d = ImageDraw.Draw(img)

    # producto sobre un panel claro (las fotos de tienda casi siempre traen fondo blanco)
    px, py, ps = 48, 55, 520
    d.rounded_rectangle((px, py, px + ps, py + ps), radius=36, fill=(255, 255, 255))
    if product_jpeg:
        try:
            p = Image.open(io.BytesIO(product_jpeg)).convert('RGB')
            p.thumbnail((ps - 60, ps - 60), Image.LANCZOS)
            img.paste(p, (px + (ps - p.width) // 2, py + (ps - p.height) // 2))
        except Exception: pass

    x, right = 620, W - 56
    chip_f = _font('dmsans.ttf', 24, 800)
    chip = cat_label.upper()
    cw = d.textlength(chip, font=chip_f) + 36
    d.rounded_rectangle((x, 62, x + cw, 104), radius=21, fill=ORANGE)
    d.text((x + 18, 83), chip, font=chip_f, fill=INK, anchor='lm')

    title_f = _font('bricolage.ttf', 44, 800)
    y = 136
    for line in _fit_lines(d, deal['title'], title_f, right - x, 3):
        d.text((x, y), line, font=title_f, fill=BONE); y += 54

    price_f = _font('bricolage.ttf', 118, 800)
    d.text((x - 4, 455), deal['price'], font=price_f, fill=MAG, anchor='ls')
    info_f = _font('dmsans.ttf', 30, 700)
    sub = f"en {deal['retailer']}" + (f"  ·  Ahorras {deal['save']}" if deal.get('save') else '')
    d.text((x, 500), sub, font=info_f, fill=BONE)

    foot_f = _font('dmsans.ttf', 26, 700)
    d.line((x, 556, right, 556), fill=(40, 60, 120), width=2)
    d.text((x, 590), 'CORILLO', font=_font('bricolage.ttf', 34, 800), fill=BONE, anchor='lm')
    d.text((right, 590), 'corillo.live/ofertas', font=foot_f, fill=MUTE, anchor='rm')

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix('.tmp.png')
    img.save(tmp, 'PNG', optimize=True); tmp.replace(out_path)


def news_card(title, label, out_path):
    """Tarjeta de la noticia del día para WhatsApp: el titular grande con la categoría."""
    img = Image.new('RGB', (W, H), INK)
    glow = Image.new('RGB', (W, H), INK); g = ImageDraw.Draw(glow)
    g.ellipse((650, -300, 1450, 400), fill=(90, 40, 20)); g.ellipse((-250, 330, 550, 950), fill=(20, 50, 120))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(130)), 0.9)
    d = ImageDraw.Draw(img)
    x, right = 72, W - 72
    chip_f = _font('dmsans.ttf', 26, 800)
    chip = ('Noticia · ' + label).upper()
    cw = d.textlength(chip, font=chip_f) + 40
    d.rounded_rectangle((x, 72, x + cw, 118), radius=23, fill=ORANGE)
    d.text((x + 20, 95), chip, font=chip_f, fill=INK, anchor='lm')
    for size in (76, 66, 58, 50):                                   # el titular más grande que quepa en 4 líneas
        f = _font('bricolage.ttf', size, 800)
        lines = _fit_lines(d, title, f, right - x, 4)
        if not lines[-1].endswith('…'): break
    y = 160
    for line in lines:
        d.text((x, y), line, font=f, fill=BONE); y += int(size * 1.12)
    d.line((x, 548, right, 548), fill=(40, 60, 120), width=2)
    d.text((x, 588), 'CORILLO', font=_font('bricolage.ttf', 36, 800), fill=BONE, anchor='lm')
    d.text((right, 588), 'corillo.live/noticias', font=_font('dmsans.ttf', 26, 700), fill=MUTE, anchor='rm')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, 'PNG', optimize=True)


def free_week_card(games, label, out_path):
    """Tarjeta de los juegos gratis de la semana en Epic para WhatsApp. games: [(título, bytes de la portada o None)], hasta 3."""
    img = Image.new('RGB', (W, H), INK)
    glow = Image.new('RGB', (W, H), INK); g = ImageDraw.Draw(glow)
    g.ellipse((700, -320, 1450, 360), fill=(95, 75, 10)); g.ellipse((-250, 360, 550, 980), fill=(20, 50, 120))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(130)), 0.9)
    d = ImageDraw.Draw(img)
    x, right = 64, W - 64
    chip_f = _font('dmsans.ttf', 26, 800)
    chip = 'GRATIS EN EPIC'
    cw = d.textlength(chip, font=chip_f) + 40
    d.rounded_rectangle((x, 56, x + cw, 102), radius=23, fill=MAG)
    d.text((x + 20, 79), chip, font=chip_f, fill=INK, anchor='lm')
    d.text((x + cw + 20, 79), label, font=_font('dmsans.ttf', 28, 700), fill=BONE, anchor='lm')
    games = games[:3]; n = len(games); gap = 28
    cw = (right - x - gap * (n - 1)) // n if n else 0
    ch = min(int(cw * 9 / 16), 300)
    top = 140 if n > 1 else 130
    tf = _font('bricolage.ttf', 34 if n > 1 else 46, 800)
    for i, (title, jpeg) in enumerate(games):
        cx = x + i * (cw + gap)
        box = Image.new('RGB', (cw, ch), (20, 40, 95))
        if jpeg:
            try:
                p = Image.open(io.BytesIO(jpeg)).convert('RGB')
                s = max(cw / p.width, ch / p.height)                   # recorta para llenar la caja sin deformar
                p = p.resize((max(cw, int(p.width * s)), max(ch, int(p.height * s))), Image.LANCZOS)
                box.paste(p.crop(((p.width - cw) // 2, (p.height - ch) // 2, (p.width - cw) // 2 + cw, (p.height - ch) // 2 + ch)))
            except Exception: pass
        mask = Image.new('L', (cw, ch), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw, ch), radius=22, fill=255)
        img.paste(box, (cx, top), mask)
        y = top + ch + 18
        for line in _fit_lines(d, title, tf, cw, 2):
            d.text((cx, y), line, font=tf, fill=BONE); y += int(tf.size * 1.1)
    d.line((x, 548, right, 548), fill=(40, 60, 120), width=2)
    d.text((x, 588), 'CORILLO', font=_font('bricolage.ttf', 36, 800), fill=BONE, anchor='lm')
    d.text((right, 588), 'corillo.live/ofertas/gratis', font=_font('dmsans.ttf', 26, 700), fill=MUTE, anchor='rm')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, 'PNG', optimize=True)
