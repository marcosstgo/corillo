// Ayudas de las páginas /overlay/ (el código de cada overlay de OBS vive en el repo corillo-bf6-overlays).
(function () {
  const OV = window.OV = {};
  OV.API = 'https://api.corillo.live/api/bf6/';
  OV.ORIGEN = location.origin;                     // las vistas previas salen del mismo sitio
  OV.PUBLICO = 'https://corillo.live/overlay/';    // lo que se copia a OBS siempre apunta a producción
  OV.fmt = n => n == null ? '—' : Number(n).toLocaleString('en-US');
  OV.esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  OV.$ = (s, r) => (r || document).querySelector(s);
  OV.json = async ruta => {
    const r = await fetch(OV.API + ruta);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error(d.error || r.status); e.data = d; e.status = r.status; throw e; }
    return d;
  };

  // Overlay real en un <iframe> a tamaño nativo, escalado para caber en su contenedor. Sin scroll, para que se vea como en OBS.
  const obs = 'ResizeObserver' in window ? new ResizeObserver(es => es.forEach(e => OV.ajustar(e.target))) : null;
  OV.frame = (el, url, w, h) => {
    el.classList.add('ov-marco'); el.dataset.mw = w; el.dataset.mh = h;
    let f = el.querySelector('iframe');
    if (!f) {
      el.replaceChildren();
      f = document.createElement('iframe');
      f.setAttribute('scrolling', 'no');
      f.title = 'Vista previa en vivo del overlay';
      f.loading = 'lazy';
      el.appendChild(f);
      if (obs) obs.observe(el.parentElement);
    }
    if (f.dataset.url !== url) { f.src = url; f.dataset.url = url; }
    OV.ajustar(el.parentElement);
  };
  OV.ajustar = caja => {
    const el = caja.querySelector(':scope > .ov-marco'); if (!el) return;
    const f = el.querySelector('iframe'); if (!f) return;
    const w = +el.dataset.mw, h = +el.dataset.mh;
    // El ancho sale de la caja: medir el marco daría su ancho anterior y una vista grande no se achicaría.
    const cs = getComputedStyle(caja), libre = caja.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const k = Math.min(1, libre / w);
    el.style.width = Math.round(w * k) + 'px';
    el.style.height = Math.round(h * k) + 'px';
    f.style.width = w + 'px'; f.style.height = h + 'px';
    f.style.transform = `scale(${k})`;
  };

  // Una caja que estaba escondida mide 0: al abrirla hay que volver a calcular.
  OV.ajustarTodo = () => document.querySelectorAll('.ov-marco').forEach(m => OV.ajustar(m.parentElement));

  OV.copiar = (btn, texto) => navigator.clipboard.writeText(texto).then(() => {
    const t = btn.dataset.txt || btn.textContent; btn.dataset.txt = t;
    btn.textContent = '¡Copiado!'; btn.classList.add('ok');
    setTimeout(() => { btn.textContent = t; btn.classList.remove('ok'); }, 1800);
  }).catch(() => { prompt('Copia este enlace:', texto); });

  // Línea con relleno. Sin ejes: la escala va en los rótulos de la página.
  OV.linea = (vals, color) => {
    if (!vals || vals.length < 2) return '<p class="ov-aviso">Reuniendo datos: la gráfica aparece en unos minutos.</p>';
    const W = 600, H = 150, pad = 8, lo = Math.min(...vals), hi = Math.max(...vals);
    const r = Math.max(hi - lo, hi * 0.04) || 1, mn = lo - (r - (hi - lo)) / 2;   // rango mínimo: 0.1 % no debe verse como un desplome
    const pts = vals.map((n, i) => [i / (vals.length - 1) * W, H - pad - (n - mn) / r * (H - pad * 2)]);
    const l = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
    const id = 'g' + Math.random().toString(36).slice(2, 7);
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Jugadores en las últimas horas">
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".38"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <path d="${l} L${W} ${H} L0 ${H} Z" fill="url(#${id})"/>
      <path d="${l}" fill="none" stroke="${color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
  };
})();
