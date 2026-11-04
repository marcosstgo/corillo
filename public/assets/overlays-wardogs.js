// /overlay/wardogs/: tarjetas de overlays, perfil de Steam y datos del juego.
// Si al servidor le falta la llave de Steam o Steam deja de dar reseñas, las tarjetas afectadas lo dicen y vuelven solas cuando regresen los datos.
(function () {
  const { $, esc, fmt, json } = OV;
  const VERDE = '#35e0a1';
  let steam = '', yo = null, juego = null, sinLlave = false;
  const cartas = [...document.querySelectorAll('.ov-carta')];

  const enlace = (c, base) => base + c.dataset.file + (c.dataset.steam ? '?steamid=' + encodeURIComponent(steam) : (c.dataset.q || ''));
  function motivo(c) {
    const d = c.dataset;
    if (d.llave && sinLlave) return ['No disponible por ahora', 'Este overlay necesita datos de Steam que no tenemos ahora mismo.'];
    if (d.resenas && juego && !(d.q ? juego.reviewsEs : juego.reviews)) return ['No disponible por ahora', 'Steam no está entregando las reseñas en este momento.'];
    if (d.steam && !steam && !d.prev) return ['Escribe tu Steam', 'Aquí verás este overlay con tus datos reales.'];
    return null;
  }
  function pintarCartas() {
    for (const c of cartas) {
      const m = motivo(c), marco = c.querySelector('.ov-escena > div'), btn = c.querySelector('[data-copiar]');
      btn.disabled = !!m || (!!c.dataset.steam && !steam);
      if (m) {
        marco.className = ''; marco.style.cssText = '';
        marco.innerHTML = `<p class="ov-falta"><b>${esc(m[0])}</b>${esc(m[1])}</p>`;
        continue;
      }
      if (marco.querySelector('.ov-falta')) marco.replaceChildren();
      const previa = c.dataset.steam && !steam ? OV.ORIGEN + '/overlay/wardogs/' + c.dataset.file + c.dataset.prev : enlace(c, OV.ORIGEN + '/overlay/wardogs/');
      OV.frame(marco, previa, +c.dataset.w, +c.dataset.h);
    }
  }
  $('#overlays').addEventListener('click', e => {
    const b = e.target.closest('[data-copiar]'); if (!b || b.disabled) return;
    OV.copiar(b, enlace(b.closest('.ov-carta'), OV.PUBLICO + 'wardogs/'));
  });

  /* ── perfil de Steam ── */
  const normalizar = t => { t = t.trim(); const m = t.match(/steamcommunity\.com\/(?:id|profiles)\/([^/?#\s]+)/i); return m ? m[1] : t.replace(/^@/, ''); };
  const decir = (t, k) => { const m = $('#msgSteam'); m.textContent = t; m.className = 'ov-msg' + (k ? ' ' + k : ''); };
  function apagarSteam() {
    sinLlave = true;
    $('#steam').disabled = true; $('#botonSteam').disabled = true;
    decir('Los overlays con tu perfil no están disponibles por ahora. Los que funcionan sin usuario siguen normal.', 'err');
    pintarCartas();
  }
  async function cargarYo(crudo, callado) {
    const v = normalizar(crudo); if (!v || sinLlave) return;
    $('#botonSteam').disabled = true; if (!callado) decir('Buscando tu perfil…');
    try {
      const d = await json('wardogs/profile?steamid=' + encodeURIComponent(v));
      steam = v; yo = d;
      try { localStorage.setItem('wd-steam', v); } catch (e) {}
      const url = new URL(location.href); url.searchParams.set('steam', v); history.replaceState(null, '', url);
      decir(`Perfil encontrado: ${d.name}.${d.hours != null ? ' ' + fmt(d.hours) + ' h en WARDOGS' : ''}${d.achievements ? ', ' + d.achievements.done + ' de ' + d.achievements.total + ' logros.' : ''}`, 'bien');
      pintarCartas(); pintarLogros();
    } catch (e) {
      const d = e.data || {};
      if (e.status === 501) return apagarSteam();
      if (d.error === 'private_profile' || d.error === 'game_details_private') decir(d.message + ' Ábrelo en Steam: Perfil, Editar perfil, Privacidad.', 'err');
      else if (d.error === 'not_found') decir('No encontramos ese perfil de Steam. Revisa el usuario o pega el enlace de tu perfil.', 'err');
      else decir('Steam no respondió. Intenta de nuevo en un momento.', 'err');
    } finally { if (!sinLlave) $('#botonSteam').disabled = false; }
  }
  $('#formSteam').addEventListener('submit', e => { e.preventDefault(); cargarYo($('#steam').value); });

  /* ── el juego ahora ── */
  async function cargarJugadores() {
    try {
      const d = await json('wardogs/players');
      $('#hJugando').textContent = fmt(d.players); $('#jugadores').textContent = fmt(d.players);
      $('#grafica').innerHTML = OV.linea(d.spark, VERDE);
      const hace = d.sinceMin >= 90 ? Math.round(d.sinceMin / 60) + ' h' : d.sinceMin + ' min';
      $('#ejeI').textContent = d.spark.length > 1 ? 'hace ' + hace : ''; $('#ejeD').textContent = d.spark.length > 1 ? 'ahora' : '';
      $('#record').textContent = fmt(d.peak);
      $('#recordNota').textContent = d.sinceMin < 1380 ? `Desde que empezamos a registrar, hace ${hace}.` : 'El máximo de las últimas 24 horas.';
      const sube = d.deltaPct >= 0;
      $('#grafCap').textContent = `Jugadores conectados en Steam. En la última media hora ${sube ? 'subió' : 'bajó'} ${Math.abs(d.deltaPct)}%.`;
    } catch (e) {}
  }
  async function cargarJuego() {
    try {
      juego = await json('wardogs/game');
      $('#kResenas').hidden = !juego.reviews;
      if (juego.reviews) {
        $('#resPct').textContent = juego.reviews.pct + '%'; $('#resBarra').style.width = juego.reviews.pct + '%';
        $('#resNota').textContent = `${juego.reviews.label || ''}, de ${fmt(juego.reviews.total)} reseñas`;
      }
      $('#precio').textContent = juego.price ? juego.price.replace(/\s*USD$/, '') : '—';
      $('#precioNota').textContent = [juego.developer && 'Desarrolla ' + juego.developer, juego.released && 'salió el ' + juego.released].filter(Boolean).join(', ');
      pintarLogros(); pintarCartas();
      const n = juego.news || [];
      $('#noticias').hidden = !n.length;
      $('#listaNoticias').innerHTML = n.map(x => `<a href="${/^https:\/\//.test(x.url) ? esc(x.url) : '#'}" target="_blank" rel="noopener"><b>${esc(x.title)}</b><span>${new Date(x.at * 1000).toLocaleDateString('es-PR', { day: 'numeric', month: 'short', year: 'numeric' })}</span></a>`).join('');
    } catch (e) {}
  }
  function pintarLogros() {
    const lista = juego && juego.achievements ? juego.achievements.slice() : [];
    $('#logros').hidden = !lista.length;
    if (!lista.length) return;
    const mios = yo && yo.achievements ? new Map(yo.achievements.list.map(a => [a.id, a])) : null;
    lista.sort((a, b) => (a.pct == null) - (b.pct == null) || a.pct - b.pct);
    $('#logrosLead').textContent = mios ? 'Los que ya tienes salen resaltados. El porcentaje es la parte de los jugadores que lo desbloqueó.' : 'El porcentaje es la parte de los jugadores que ya lo desbloqueó, según Steam.';
    const tope = Math.max(...lista.map(a => a.pct || 0), 1);
    $('#tablaLogros').innerHTML = lista.map(a => {
      const lo = mios && mios.get(a.id) && mios.get(a.id).unlocked, p = a.pct;
      const src = mios && !lo ? (a.iconGray || a.icon) : a.icon;
      return `<div class="ov-logro ${mios ? (lo ? 'tengo' : 'falta') : ''} ${p != null && p < 5 ? 'raro' : ''}"><img src="${/^https:\/\//.test(src || '') ? esc(src) : ''}" alt="" loading="lazy">
        <div><h3>${esc(a.name)}</h3><p>${esc(a.desc || 'Logro oculto')}</p><div class="ov-barra"><i style="width:${p == null ? 0 : Math.max(2, p / tope * 100)}%"></i></div></div>
        <div class="ov-logro-pct">${p == null ? '—' : (p < 10 ? p.toFixed(1) : Math.round(p)) + '%'}<small>${lo ? 'lo tienes' : 'lo tiene'}</small></div></div>`;
    }).join('');
  }

  /* ── arranque ── */
  pintarCartas(); cargarJugadores();
  setInterval(cargarJugadores, 60000); setInterval(cargarJuego, 10 * 60000);
  cargarJuego().finally(async () => {
    // ¿Hay llave de Steam en el servidor? Sin ella responde 501 enseguida, sin llamar a Steam.
    try { await json('wardogs/profile?steamid=0'); } catch (e) { if (e.status === 501) return apagarSteam(); }
    let s = new URL(location.href).searchParams.get('steam');
    if (!s) { try { s = localStorage.getItem('wd-steam'); } catch (e) {} }
    if (s) { $('#steam').value = s; cargarYo(s, true); }
  });
})();
