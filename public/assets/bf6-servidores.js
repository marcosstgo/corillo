// Servidores de Battlefield 6 en vivo y cuántos juegan en Steam (10-nov-2026). Lo usan /bf6/ y /overlay/bf6/.
// Necesita overlays.js (window.OV) antes. La región inicial sale de data-region en #servidores.
(function () {
  const { $, esc, fmt, json } = window.OV;
  const caja = $('#servidores'); if (!caja) return;
  const poner = (sel, v) => document.querySelectorAll(sel).forEach(el => { el.textContent = v; });

  /* ── cuántos juegan ── */
  const jugando = () => json('players').then(d => { poner('[data-bf6="steam"]', fmt(d.players)); }).catch(() => {});
  jugando(); setInterval(jugando, 60000);

  /* ── servidores ── */
  const SV = { region: caja.dataset.region || 'all', modo: 'all', q: '', vistos: 12, datos: null };
  const REG = { 'North America': 'Norteamérica', 'South America': 'Sudamérica', Europe: 'Europa', Asia: 'Asia', Oceania: 'Oceanía' };
  const PLAT = { steam: 'Steam', pc: 'EA App', ps5: 'PS5', ps4: 'PS4', xboxseries: 'Xbox Series', xboxone: 'Xbox One', xbox: 'Xbox' };
  const chip = (k, v, txt, on) => `<button class="ov-chip" type="button" data-k="${k}" data-v="${esc(v)}" aria-pressed="${on}">${esc(txt)}</button>`;
  async function cargar() {
    try {
      SV.datos = await json('servers?region=' + encodeURIComponent(SV.region) + (SV.q ? '&q=' + encodeURIComponent(SV.q) : ''));
      poner('[data-bf6="servidores"]', fmt(SV.datos.withPlayers));
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

})();
