// /overlay/bf6/: generador de enlaces para OBS y servidores en vivo.
(function () {
  const { $, esc, fmt, json } = OV;
  const EJEMPLO = 'katat0nia';
  const PLATS = [...document.querySelectorAll('#plataformas .ov-chip')].map(b => [b.dataset.p, b.textContent]);
  const estado = { tipo: null, plat: 'ea' };
  let filas = 0, reloj = null;

  /* ── generador ── */
  function elegirTipo(b) {
    estado.tipo = b;
    document.querySelectorAll('.ov-tipo').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    const multi = !!b.dataset.multi;
    $('#unJugador').hidden = multi; $('#escuadron').hidden = !multi;
    $('#pasoTitulo').textContent = multi ? 'Tu escuadrón' : 'Tu usuario';
    if (multi && !filas) { otraFila(); otraFila(); }
    pintar();
  }
  function otraFila() {
    if (filas >= 4) return;
    const i = ++filas, d = document.createElement('div');
    d.className = 'ov-jugador';
    d.innerHTML = `<input class="ov-campo" placeholder="Jugador" aria-label="Jugador ${i}" autocomplete="off" spellcheck="false"><select class="ov-campo" aria-label="Plataforma">${PLATS.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</select><button class="ov-quitar" type="button" aria-label="Quitar jugador"><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>`;
    $('#filas').appendChild(d);
    d.querySelector('input').addEventListener('input', () => programar());
    d.querySelector('select').addEventListener('change', () => programar(true));
    d.querySelector('.ov-quitar').addEventListener('click', () => { d.remove(); filas--; $('#otroJugador').hidden = false; programar(true); });
    $('#otroJugador').hidden = filas >= 4;
  }
  function escuadron() {
    const nombres = [], plats = [];
    document.querySelectorAll('.ov-jugador').forEach(r => {
      const n = r.querySelector('input').value.trim();
      if (n) { nombres.push(n); plats.push(r.querySelector('select').value); }
    });
    return { nombres, plats };
  }
  // El enlace de la persona, o null si todavía falta su usuario (entonces se enseña el ejemplo, sin enlace que copiar).
  function ruta(ejemplo) {
    const t = estado.tipo.dataset;
    if (t.multi) {
      const { nombres, plats } = ejemplo ? { nombres: [EJEMPLO, EJEMPLO], plats: ['ea', 'ea'] } : escuadron();
      if (nombres.length < 2) return null;
      return `multi.html?names=${nombres.map(encodeURIComponent).join(',')}&platforms=${plats.join(',')}`;
    }
    const n = ejemplo ? EJEMPLO : $('#nombre').value.trim();
    if (!n) return null;
    if (t.ea) return `${t.id}.html?name=${encodeURIComponent(n)}`;
    return `${t.id}.html?name=${encodeURIComponent(n)}&platform=${ejemplo ? 'ea' : estado.plat}`;
  }
  function medidas() {
    const t = estado.tipo.dataset;
    if (!t.multi) return [+t.w, +t.h];
    const n = Math.max(escuadron().nombres.length, 2);
    return [n * 270 + (n - 1) * 8, +t.h];
  }
  function pintar() {
    const mia = ruta(false), [w, h] = medidas();
    OV.frame($('#vista'), `${OV.ORIGEN}/overlay/bf6/${mia || ruta(true)}`, w, h);
    $('#rotulo').textContent = mia ? 'Vista previa' : `Ejemplo con ${EJEMPLO}`;
    $('#sinEnlace').hidden = !!mia; $('#conEnlace').hidden = !mia;
    if (mia) { $('#enlace').value = `${OV.PUBLICO}bf6/${mia}`; $('#medidas').textContent = `${w} × ${h}`; }
  }
  function programar(ya) { clearTimeout(reloj); reloj = setTimeout(pintar, ya ? 0 : 650); }

  $('#tipos').addEventListener('click', e => { const b = e.target.closest('.ov-tipo'); if (b) elegirTipo(b); });
  $('#plataformas').addEventListener('click', e => {
    const b = e.target.closest('.ov-chip'); if (!b) return;
    estado.plat = b.dataset.p;
    document.querySelectorAll('#plataformas .ov-chip').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    programar(true);
  });
  $('#nombre').addEventListener('input', () => programar());
  $('#otroJugador').addEventListener('click', () => { otraFila(); programar(); });
  $('#copiar').addEventListener('click', e => OV.copiar(e.currentTarget, $('#enlace').value));
  elegirTipo(document.querySelector('.ov-tipo[aria-pressed="true"]'));

  if (new URLSearchParams(location.search).get('game') === 'wardogs') location.replace('/overlay/wardogs/');   // enlaces viejos
})();
