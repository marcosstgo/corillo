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

  /* ── cuántos juegan ── */
  const jugando = () => json('players').then(d => { $('#hSteam').textContent = fmt(d.players); }).catch(() => {});
  jugando(); setInterval(jugando, 60000);

  /* ── servidores ── */
  const SV = { region: 'all', modo: 'all', q: '', vistos: 12, datos: null };
  const REG = { 'North America': 'Norteamérica', 'South America': 'Sudamérica', Europe: 'Europa', Asia: 'Asia', Oceania: 'Oceanía' };
  const PLAT = { steam: 'Steam', pc: 'EA App', ps5: 'PS5', ps4: 'PS4', xboxseries: 'Xbox Series', xboxone: 'Xbox One', xbox: 'Xbox' };
  const chip = (k, v, txt, on) => `<button class="ov-chip" type="button" data-k="${k}" data-v="${esc(v)}" aria-pressed="${on}">${esc(txt)}</button>`;
  async function cargar() {
    try {
      SV.datos = await json('servers?region=' + encodeURIComponent(SV.region) + (SV.q ? '&q=' + encodeURIComponent(SV.q) : ''));
      $('#hSrv').textContent = fmt(SV.datos.withPlayers);
      dibujar();
    } catch (e) {
      $('#srvs').innerHTML = '<p class="ov-aviso"><b>No pudimos cargar los servidores.</b> Se vuelve a intentar solo en un minuto.</p>';
    }
  }
  function dibujar() {
    const d = SV.datos; if (!d) return;
    $('#regiones').innerHTML = chip('region', 'all', 'Todas', SV.region === 'all') + Object.keys(REG).filter(r => d.regions[r] || SV.region === r).map(r => chip('region', r, REG[r], SV.region === r)).join('');
    $('#modos').innerHTML = chip('modo', 'all', 'Todos los modos', SV.modo === 'all') + Object.entries(d.modes).sort((a, b) => b[1] - a[1]).map(([m, n]) => chip('modo', m, `${m} (${n})`, SV.modo === m)).join('');
    const lista = d.servers.filter(x => SV.modo === 'all' || x.mode === SV.modo);
    $('#srvs').innerHTML = lista.length ? lista.slice(0, SV.vistos).map(x => {
      const lleno = x.max && x.players >= x.max, pct = x.max ? Math.min(100, x.players / x.max * 100) : 0;
      // La imagen viene de una API externa: va como <img> para que un valor raro no pueda romper el estilo.
      const img = /^https:\/\//.test(x.img || '') ? `<img src="${esc(x.img)}" alt="" loading="lazy">` : '';
      return `<article class="ov-srv"><div class="ov-srv-foto">${img}<span class="ov-srv-mapa">${esc(x.map || 'Mapa desconocido')}</span>${lleno ? '<span class="ov-srv-lleno">Lleno</span>' : ''}</div>
        <div class="ov-srv-txt"><h3 title="${esc(x.name)}">${esc(x.name)}</h3>
        <div class="ov-srv-tags"><span>${esc(x.mode || '')}</span><span>${esc(REG[x.region] || x.region || '')}</span>${x.platform ? `<span>${esc(PLAT[x.platform] || x.platform)}</span>` : ''}</div>
        <div class="ov-srv-cuenta">${esc(x.players)}<small> de ${esc(x.max)} jugadores</small></div><div class="ov-barra"><i style="width:${pct}%"></i></div></div></article>`;
    }).join('') : '<p class="ov-aviso"><b>No hay servidores con ese filtro.</b> Prueba otra región, otro modo o borra la búsqueda.</p>';
    $('#srvMas').hidden = lista.length <= SV.vistos;
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('#regiones .ov-chip, #modos .ov-chip'); if (!b) return;
    SV[b.dataset.k] = b.dataset.v; SV.vistos = 12;
    if (b.dataset.k === 'region') cargar(); else dibujar();
  });
  $('#srvMas').addEventListener('click', () => { SV.vistos += 12; dibujar(); });
  let qt;
  $('#srvQ').addEventListener('input', e => { clearTimeout(qt); qt = setTimeout(() => { SV.q = e.target.value.trim(); SV.vistos = 12; cargar(); }, 500); });
  cargar(); setInterval(cargar, 60000);

  if (new URLSearchParams(location.search).get('game') === 'wardogs') location.replace('/overlay/wardogs/');   // enlaces viejos
})();
