/* Buscador del Mercado: filtros → /api/mercado/anuncios → tarjetas (mismo HTML que components/mercado/Card.astro).
   Los filtros viven en la URL (?q=…&pueblo=…), así un resultado se puede compartir. */
(function () {
  var f = document.querySelector('[data-lista]');
  if (!f) return;
  var grid = document.querySelector('[data-grid]'), vacio = document.querySelector('[data-empty]');
  var count = document.querySelector('[data-count]'), mas = document.querySelector('[data-more]');
  var PUEBLOS = {};
  try { PUEBLOS = JSON.parse(document.getElementById('mkPueblos').textContent); } catch (e) {}
  var LANG = f.dataset.lang || 'es', CAT = f.dataset.categoria || '';
  var pref = LANG === 'es' ? '' : '/' + LANG;
  var pagina = 1, total = 0, pedido = 0;
  var esc = function (v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var precio = function (n) { return n === 0 ? t('mercado.gratis') : '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 }); };

  function tarjeta(a) {
    var href = pref + '/mercado/a/' + a.id + '/', v = a.vendedor, vendido = a.estado === 'vendido';
    return '<article class="of-card mk-card" data-estado="' + esc(a.estado) + '">' +
      '<a class="of-pic mk-pic" href="' + href + '" aria-label="' + esc(a.titulo) + '">' +
      (a.fotos[0] ? '<img src="' + esc(a.fotos[0]) + '" alt="" width="400" height="300" loading="lazy" decoding="async">' : '') +
      '<span class="of-flag" style="--tc:var(--h2-bone)">' + esc(t('mercado.condicion.' + a.condicion)) + '</span>' +
      (vendido ? '<span class="mk-sold">' + esc(t('mercado.vendido_marca')) + '</span>' : '') +
      (a.estado === 'reservado' ? '<span class="mk-res">' + esc(t('mercado.reservado_marca')) + '</span>' : '') + '</a>' +
      '<div class="of-body"><h3><a href="' + href + '">' + esc(a.titulo) + '</a></h3>' +
      '<div class="of-price"><b>' + esc(precio(a.precio)) + '</b>' + (a.negociable && !vendido ? '<em>' + esc(t('mercado.negociable')) + '</em>' : '') + '</div>' +
      '<div class="of-meta mk-meta"><span>' + esc(PUEBLOS[a.pueblo] || a.pueblo) + '</span><span>' + esc(t('mercado.entrega_op.' + a.entrega)) + '</span></div>' +
      '<div class="mk-who"><span class="mk-ava" style="--c:' + esc(v.color || 'var(--h2-cyan)') + '">' +
      (v.avatar ? '<img src="' + esc(v.avatar) + '" alt="" width="24" height="24" loading="lazy">' : esc((v.nombre || '?').slice(0, 1))) + '</span>' +
      '<span class="mk-name">' + esc(v.nombre) + '</span>' +
      (v.streamer ? '<span class="mk-badge" title="' + esc(t('mercado.streamer_badge_t')) + '">' + esc(t('mercado.streamer_badge')) + '</span>' : '') +
      '</div></div></article>';
  }

  function params() {
    var p = new URLSearchParams();
    new FormData(f).forEach(function (v, k) {
      if (!v) return;
      if (k === 'condicion') p.set(k, (p.get(k) ? p.get(k) + ',' : '') + v); else p.set(k, v);
    });
    if (p.get('orden') === 'recientes') p.delete('orden');
    if (p.get('orden') !== 'cercania') p.delete('cerca');
    return p;
  }
  function activos(p) { var n = 0; p.forEach(function (_, k) { if (k !== 'q') n++; }); return n; }

  function buscar(añadir) {
    var p = params(), id = ++pedido;
    var q = new URLSearchParams(p);
    if (CAT) q.set('categoria', CAT);
    q.set('pagina', String(pagina));
    history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p.toString() : ''));
    var badge = f.querySelector('.mk-fil-n'), n = activos(p);
    badge.hidden = !n; badge.textContent = n;
    count.textContent = t('comun.cargando');
    fetch('/api/mercado/anuncios?' + q.toString()).then(function (r) { return r.json(); }).then(function (j) {
      if (id !== pedido) return;
      total = j.total;
      var html = j.items.map(tarjeta).join('');
      if (añadir) grid.insertAdjacentHTML('beforeend', html); else grid.innerHTML = html;
      vacio.hidden = total > 0;
      if (!total && p.toString()) vacio.textContent = t('mercado.sin_resultados');
      count.textContent = p.toString() ? t('mercado.resultados', { n: total }) : '';
      mas.hidden = grid.children.length >= total;
    }).catch(function () { if (id === pedido) count.textContent = t('comun.sin_conexion'); });
  }

  // Estado inicial desde la URL
  var u = new URLSearchParams(location.search);
  u.forEach(function (v, k) {
    if (k === 'condicion') v.split(',').forEach(function (c) { var el = f.querySelector('[name=condicion][value="' + c + '"]'); if (el) el.checked = true; });
    else if (f.elements[k]) f.elements[k].value = v;
  });
  var cerca = f.querySelector('[data-cerca]');
  function verCerca() { cerca.hidden = f.orden.value !== 'cercania'; }
  verCerca();
  if ([].some.call(f.querySelectorAll('.mk-fil-grid [name]'), function (el) { return el.type === 'checkbox' ? el.checked : el.value && el.name !== 'orden' || (el.name === 'orden' && el.value !== 'recientes'); })) f.querySelector('details').open = true;
  if (u.toString()) buscar(false);
  else if (grid.children.length) {
    // Sin filtros: el HTML ya trae los anuncios del último build; se completa por si hay más nuevos.
    buscar(false);
  }

  f.addEventListener('submit', function (e) { e.preventDefault(); pagina = 1; buscar(false); });
  f.addEventListener('change', function (e) { if (e.target.name === 'orden') verCerca(); if (e.target.name !== 'q') { pagina = 1; buscar(false); } });
  f.addEventListener('reset', function () { setTimeout(function () { verCerca(); pagina = 1; buscar(false); }, 0); });
  mas.addEventListener('click', function () { pagina++; buscar(true); });
})();
