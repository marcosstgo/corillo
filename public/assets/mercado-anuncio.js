/* Página de un anuncio del Mercado: contactar al vendedor, ver su WhatsApp y reportar.
   Cada acción lleva su propio widget de Cloudflare Turnstile (render explícito, acción propia);
   el token es de un solo uso, así que el widget se reinicia después de cada envío.
   La API valida el token con siteverify: aquí solo se obtiene. */
(function () {
  var root = document.querySelector('[data-anuncio]');
  if (!root) return;
  var ID = root.getAttribute('data-anuncio');
  var SITEKEY = root.getAttribute('data-turnstile');
  var API = '/api/mercado/anuncios/' + encodeURIComponent(ID);
  var widgets = {};

  function tsListo(cb) {
    if (window.turnstile) return cb();
    var t = setInterval(function () { if (window.turnstile) { clearInterval(t); cb(); } }, 100);
  }
  function widget(accion, el, alToken) {
    tsListo(function () {
      if (widgets[accion] !== undefined) { window.turnstile.reset(widgets[accion]); return; }
      widgets[accion] = window.turnstile.render(el, {
        sitekey: SITEKEY, action: accion, theme: 'dark', language: window.LANG || 'es',
        callback: function (tok) { if (alToken) alToken(tok); },
        'expired-callback': function () { window.turnstile.reset(widgets[accion]); },
      });
    });
  }
  function token(accion) {
    return widgets[accion] !== undefined && window.turnstile ? window.turnstile.getResponse(widgets[accion]) || '' : '';
  }
  function reset(accion) { if (widgets[accion] !== undefined && window.turnstile) window.turnstile.reset(widgets[accion]); }
  function post(ruta, datos) {
    return fetch(API + ruta, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, j: j }; }); })
      .catch(function () { return { ok: false, j: { detail: t('comun.sin_conexion') } }; });
  }
  function aviso(el, texto, bien) { el.textContent = texto; el.hidden = !texto; el.dataset.ok = bien ? '1' : ''; }
  function abrir(dlg) { if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); }
  document.querySelectorAll('dialog [data-cerrar]').forEach(function (b) {
    b.addEventListener('click', function () { b.closest('dialog').close(); });
  });

  // ── Contactar ──
  var dC = document.getElementById('mkContacto');
  var fC = dC && dC.querySelector('form');
  document.querySelectorAll('[data-contactar]').forEach(function (b) {
    b.addEventListener('click', function () { abrir(dC); widget('contacto', dC.querySelector('.mk-ts')); });
  });
  if (fC) fC.addEventListener('submit', function (e) {
    e.preventDefault();
    var out = fC.querySelector('.mk-out'), btn = fC.querySelector('[type=submit]');
    var tok = token('contacto');
    if (!tok) return aviso(out, t('mercado.espera_verificacion'));
    btn.disabled = true; aviso(out, '');
    post('/contacto', { nombre: fC.nombre.value, email: fC.email.value, mensaje: fC.mensaje.value, website: fC.website.value, token: tok })
      .then(function (r) {
        btn.disabled = false; reset('contacto');
        if (r.ok) { fC.reset(); aviso(out, r.j.mensaje || t('mercado.enviar_mensaje'), true); }
        else aviso(out, typeof r.j.detail === 'string' ? r.j.detail : t('mercado.error_datos'));
      });
  });

  // ── WhatsApp: el número no está en la página; se pide a la API tras Turnstile ──
  var dW = document.getElementById('mkWhatsapp');
  document.querySelectorAll('[data-wa]').forEach(function (b) {
    b.addEventListener('click', function () {
      abrir(dW);
      var out = dW.querySelector('.mk-out'), res = dW.querySelector('.mk-wa');
      aviso(out, ''); res.hidden = true; dW.querySelector('.mk-ts').hidden = false;
      widget('whatsapp', dW.querySelector('.mk-ts'), function (tok) {
        post('/whatsapp', { token: tok }).then(function (r) {
          reset('whatsapp');
          if (!r.ok) return aviso(out, r.j.detail || t('mercado.error_datos'));
          var n = r.j.whatsapp, bonito = '(' + n.slice(0, 3) + ') ' + n.slice(3, 6) + '-' + n.slice(6);
          var texto = t('mercado.whatsapp_texto', { titulo: root.getAttribute('data-titulo') });
          res.querySelector('b').textContent = bonito;
          res.querySelector('a').href = 'https://wa.me/1' + n + '?text=' + encodeURIComponent(texto);
          res.hidden = false;
          dW.querySelector('.mk-ts').hidden = true;
        });
      });
    });
  });

  // ── Reportar ──
  var dR = document.getElementById('mkReporte');
  var fR = dR && dR.querySelector('form');
  document.querySelectorAll('[data-reportar]').forEach(function (b) {
    b.addEventListener('click', function () { abrir(dR); widget('reporte', dR.querySelector('.mk-ts')); });
  });
  if (fR) fR.addEventListener('submit', function (e) {
    e.preventDefault();
    var out = fR.querySelector('.mk-out'), btn = fR.querySelector('[type=submit]');
    var tok = token('reporte');
    if (!tok) return aviso(out, t('mercado.espera_verificacion'));
    btn.disabled = true;
    post('/reporte', { motivo: fR.motivo.value, detalle: fR.detalle.value, token: tok }).then(function (r) {
      btn.disabled = false; reset('reporte');
      aviso(out, r.ok ? r.j.mensaje : (r.j.detail || t('mercado.error_datos')), r.ok);
      if (r.ok) fR.reset();
    });
  });
})();
