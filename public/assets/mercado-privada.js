/* Mis anuncios · Moderación · Anuncio recién creado (antes de que exista su página estática). */
(function () {
  var root = document.querySelector('[data-privada]');
  if (!root) return;
  var MODO = root.dataset.privada, LANG = root.dataset.lang || 'es', pref = LANG === 'es' ? '' : '/' + LANG;
  var cuerpo = root.querySelector('[data-cuerpo]'), h1 = root.querySelector('[data-h1]');
  var PUEBLOS = {}; try { PUEBLOS = JSON.parse(document.getElementById('mkPueblos').textContent); } catch (e) {}
  var esc = function (v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var precio = function (n) { return n === 0 ? t('mercado.gratis') : '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 }); };
  var vacio = function (txt, extra) { cuerpo.innerHTML = '<div class="of-empty">' + esc(txt) + (extra || '') + '</div>'; };
  var pedirLogin = function () {
    vacio(t('mercado.login_txt'), ' <a class="mk-sell" style="margin-left:8px" href="' + pref + '/mercado/vender/">' + esc(t('comun.entrar')) + '</a>');
  };

  function fila(a, admin) {
    var badges = [];
    if (a.estado !== 'disponible') badges.push('<span class="mk-state ' + a.estado + '">' + esc(t('mercado.estado.' + a.estado)) + '</span>');
    if (a.pausado) badges.push('<span class="mk-tag">' + esc(t('mercado.pausado')) + '</span>');
    if (a.moderacion === 'oculto') badges.push('<span class="mk-tag mk-tag-mal" title="' + esc(a.motivo_oculto) + '">' + esc(t('mercado.oculto')) + '</span>');
    if (a.reportes) badges.push('<span class="mk-tag mk-tag-mal">' + esc(t('mercado.mod_reportes', { n: a.reportes })) + '</span>');
    var acciones = admin
      ? (a.moderacion === 'oculto' || a.reportes ? '<button class="mk-btn" data-mod="aprobar">' + esc(t('mercado.mod_aprobar')) + '</button>' : '') +
        (a.moderacion !== 'oculto' ? '<button class="mk-btn" data-mod="ocultar">' + esc(t('mercado.mod_ocultar')) + '</button>' : '') +
        '<button class="mk-btn mk-btn-mal" data-mod="banear">' + esc(t('mercado.mod_banear')) + '</button>'
      : '<label class="mk-sel">' + esc(t('mercado.marcar')) + ' <select data-estado>' +
        ['disponible', 'reservado', 'vendido'].map(function (e) { return '<option value="' + e + '"' + (e === a.estado ? ' selected' : '') + '>' + esc(t('mercado.estado.' + e)) + '</option>'; }).join('') + '</select></label>' +
        '<button class="mk-btn" data-pausa="' + (a.pausado ? '0' : '1') + '">' + esc(t(a.pausado ? 'mercado.reanudar' : 'mercado.pausar')) + '</button>' +
        '<a class="mk-btn" href="' + pref + '/mercado/vender/?id=' + a.id + '">' + esc(t('comun.editar')) + '</a>' +
        '<button class="mk-btn mk-btn-mal" data-borrar>' + esc(t('comun.borrar')) + '</button>';
    var reps = admin && a.lista_reportes && a.lista_reportes.length
      ? '<ul class="mk-reps">' + a.lista_reportes.map(function (r) { return '<li><b>' + esc(t('mercado.motivo.' + r.motivo)) + '</b>' + (r.detalle ? ': ' + esc(r.detalle) : '') + '</li>'; }).join('') + '</ul>' : '';
    return '<article class="mk-row" data-id="' + a.id + '">' +
      '<a class="mk-row-pic" href="' + pref + '/mercado/a/' + a.id + '/">' + (a.fotos[0] ? '<img src="' + esc(a.fotos[0]) + '" alt="" loading="lazy">' : '') + '</a>' +
      '<div class="mk-row-b"><h3><a href="' + pref + '/mercado/a/' + a.id + '/">' + esc(a.titulo) + '</a></h3>' +
      '<p class="of-meta">' + esc(precio(a.precio)) + ' · ' + esc(PUEBLOS[a.pueblo] || a.pueblo) + (admin ? ' · ' + esc(a.vendedor.nombre) + ' (@' + esc(a.vendedor.key) + ')' : '') + '</p>' +
      (badges.length ? '<p class="mk-badges">' + badges.join('') + '</p>' : '') + reps +
      '<div class="mk-acts">' + acciones + '</div><p class="mk-out" role="status" hidden></p></div></article>';
  }

  // ── Mis anuncios ──
  function misAnuncios() {
    if (!MkCuenta.sesion()) return pedirLogin();
    MkCuenta.api('/mis-anuncios').then(function (r) {
      if (!r.ok) return r.status === 401 ? pedirLogin() : vacio(r.j.detail || t('comun.sin_conexion'));
      var items = r.j.items, activos = items.filter(function (a) { return a.estado !== 'vendido'; }).length;
      if (!items.length) return vacio(t('mercado.mis_vacio'), ' <a class="mk-sell" style="margin-left:8px" href="' + pref + '/mercado/vender/">' + esc(t('mercado.vender')) + '</a>');
      cuerpo.innerHTML = '<p class="of-meta">' + esc(t('mercado.mis_activos', { n: activos, max: r.j.max_activos })) + '</p><div class="mk-rows">' + items.map(function (a) { return fila(a, false); }).join('') + '</div>';
      MkCuenta.api('/yo').then(function (y) {
        if (y.ok && y.j.admin) cuerpo.insertAdjacentHTML('afterbegin', '<p><a class="mk-link" href="' + pref + '/mercado/moderacion/">' + esc(t('mercado.moderacion')) + '</a></p>');
      });
    });
  }
  function actualizar(row, r) {
    if (!r.ok) { var o = row.querySelector('.mk-out'); o.textContent = r.j.detail || t('mercado.error_datos'); o.hidden = false; return; }
    if (r.status === 204) { row.remove(); return; }
    row.outerHTML = fila(Object.assign(r.j, { lista_reportes: [] }), MODO === 'moderacion');
  }
  cuerpo.addEventListener('change', function (e) {
    if (!e.target.matches('[data-estado]')) return;
    var row = e.target.closest('[data-id]');
    MkCuenta.api('/anuncios/' + row.dataset.id + '/estado', { method: 'POST', json: { estado: e.target.value } }).then(function (r) { actualizar(row, r); });
  });
  cuerpo.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var row = b.closest('[data-id]'), id = row && row.dataset.id; if (!id) return;
    if (b.dataset.pausa !== undefined) MkCuenta.api('/anuncios/' + id + '/pausa', { method: 'POST', json: { pausado: b.dataset.pausa === '1' } }).then(function (r) { actualizar(row, r); });
    else if (b.dataset.borrar !== undefined) { if (confirm(t('mercado.borrar_confirmar'))) MkCuenta.api('/anuncios/' + id, { method: 'DELETE' }).then(function (r) { actualizar(row, r); }); }
    else if (b.dataset.mod) {
      if (b.dataset.mod === 'banear' && !confirm(t('mercado.mod_banear_confirmar'))) return;
      MkCuenta.api('/moderacion/' + id, { method: 'POST', json: { accion: b.dataset.mod } }).then(function (r) { if (b.dataset.mod === 'banear' && r.ok) moderacion(); else actualizar(row, r); });
    }
  });

  // ── Moderación ──
  function moderacion() {
    if (!MkCuenta.sesion()) return pedirLogin();
    MkCuenta.api('/moderacion').then(function (r) {
      if (!r.ok) return r.status === 401 ? pedirLogin() : vacio(r.status === 403 ? t('mercado.solo_admin') : (r.j.detail || t('comun.sin_conexion')));
      cuerpo.innerHTML = '<section class="of-sec"><h2>' + esc(t('mercado.mod_pendientes')) + '</h2>' +
        (r.j.pendientes.length ? '<div class="mk-rows">' + r.j.pendientes.map(function (a) { return fila(a, true); }).join('') + '</div>' : '<p class="of-empty">' + esc(t('mercado.mod_vacio')) + '</p>') +
        '</section><section class="of-sec"><h2>' + esc(t('mercado.mod_recientes')) + '</h2><div class="mk-rows">' + r.j.recientes.map(function (a) { return fila(a, true); }).join('') + '</div></section>';
    });
  }

  // ── Anuncio recién creado: vista mínima y recarga cuando la página estática ya existe ──
  function anuncio() {
    var m = location.pathname.match(/\/mercado\/a\/([a-z0-9]{15})\/?$/);
    if (!m) { h1.textContent = t('mercado.no_disponible'); return vacio(t('mercado.no_disponible_txt')); }
    MkCuenta.api('/anuncios/' + m[1]).then(function (r) {
      if (!r.ok) {
        h1.textContent = t('mercado.no_disponible');
        document.title = t('mercado.no_disponible') + ' — CORILLO';
        return vacio(t('mercado.no_disponible_txt'), ' <a class="mk-link" href="' + pref + '/mercado/">' + esc(t('mercado.ver_todo')) + '</a>');
      }
      var a = r.j;
      h1.textContent = a.titulo;
      document.title = a.titulo + ' — ' + precio(a.precio) + ' | ' + t('mercado.nombre') + ' CORILLO';
      cuerpo.innerHTML = '<div class="mk-ad"><div class="mk-galw"><div class="mk-gal">' + a.fotos.map(function (f) { return '<img src="' + esc(f) + '" alt="">'; }).join('') + '</div></div>' +
        '<aside class="mk-side"><div class="of-price"><b>' + esc(precio(a.precio)) + '</b>' + (a.negociable ? '<em>' + esc(t('mercado.negociable')) + '</em>' : '') + '</div>' +
        '<p class="of-meta">' + esc(t('mercado.condicion.' + a.condicion)) + ' · ' + esc(PUEBLOS[a.pueblo] || a.pueblo) + ' · ' + esc(t('mercado.entrega_op.' + a.entrega)) + '</p>' +
        '<p class="of-empty">' + esc(t('mercado.f_pagina_pronto')) + '</p></aside></div>';
      // Cuando el sitio se recompila, esta misma URL ya sirve la página completa (sin data-fallback).
      var intentos = 0, tick = setInterval(function () {
        if (++intentos > 30) return clearInterval(tick);
        fetch(location.pathname, { cache: 'no-store' }).then(function (x) { return x.text(); }).then(function (html) {
          if (html.indexOf('data-fallback') === -1 && html.indexOf('data-anuncio') !== -1) location.reload();
        }).catch(function () {});
      }, 10000);
    });
  }

  ({ 'mis-anuncios': misAnuncios, moderacion: moderacion, anuncio: anuncio })[MODO]();
})();
