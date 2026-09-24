/* Publicar / editar un anuncio (?id=<id> para editar). */
(function () {
  var root = document.querySelector('[data-vender]');
  if (!root) return;
  var LANG = root.dataset.lang || 'es', pref = LANG === 'es' ? '' : '/' + LANG;
  var CATS = JSON.parse(document.getElementById('mkCats').textContent);
  var login = root.querySelector('[data-login]'), form = root.querySelector('[data-form]');
  var cargando = root.querySelector('[data-cargando]'), thumbs = form.querySelector('[data-thumbs]');
  var editId = new URLSearchParams(location.search).get('id');
  var fotos = [], fotosCambiaron = false, MAX = 10;
  var esc = function (v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  function aviso(el, txt, ok) { el.textContent = txt || ''; el.hidden = !txt; el.dataset.ok = ok ? '1' : ''; }

  // ── Sesión ──
  function mostrar() {
    var s = MkCuenta.sesion();
    cargando.hidden = true;
    if (!s) { login.hidden = false; form.hidden = true; return; }
    login.hidden = true; form.hidden = false;
    if (editId) cargarEdicion();
  }
  login.querySelector('form').addEventListener('submit', function (e) {
    e.preventDefault();
    var f = e.target, out = f.querySelector('.mk-out'), b = f.querySelector('[type=submit]');
    b.disabled = true; aviso(out, '');
    MkCuenta.entrar(f.email.value.trim(), f.password.value).then(mostrar).catch(function (err) {
      aviso(out, /confirma|verif|expulsad/i.test(err.message) ? err.message : t('mercado.login_error'));
    }).then(function () { b.disabled = false; });
  });

  // ── Categoría → tipos ──
  var subL = form.querySelector('[data-sub]');
  function llenarSub(valor) {
    var c = CATS.find(function (x) { return x.slug === form.categoria.value; });
    subL.hidden = !c || !c.sub.length;
    form.subcategoria.innerHTML = c && c.sub.length ? '<option value="">' + esc(t('mercado.f_sub_ninguna')) + '</option>' +
      c.sub.map(function (s) { return '<option value="' + s.slug + '">' + esc(s.nombre) + '</option>'; }).join('') : '';
    if (valor) form.subcategoria.value = valor;
  }
  form.categoria.addEventListener('change', function () { llenarSub(''); });

  // ── Fotos: se reducen aquí (≤2000 px, JPEG) para subir rápido; el servidor las vuelve a procesar ──
  function reducir(file) {
    var max = 2000;
    var bmp = window.createImageBitmap ? createImageBitmap(file, { imageOrientation: 'from-image' }) : Promise.reject();
    return bmp.then(function (b) {
      var k = Math.min(1, max / Math.max(b.width, b.height));
      var c = document.createElement('canvas');
      c.width = Math.round(b.width * k); c.height = Math.round(b.height * k);
      c.getContext('2d').drawImage(b, 0, 0, c.width, c.height);
      return new Promise(function (ok) { c.toBlob(function (bl) { ok(bl || file); }, 'image/jpeg', 0.9); });
    }).catch(function () { return file; });   // navegador viejo: se sube tal cual (el servidor igual la reduce)
  }
  function pintar() {
    thumbs.innerHTML = fotos.map(function (f, i) {
      return '<li class="mk-th"><img src="' + f.url + '" alt="">' + (i === 0 ? '<span class="mk-th-cover">' + esc(t('mercado.f_portada')) + '</span>' : '') +
        '<div class="mk-th-b"><button type="button" data-m="-1" data-i="' + i + '" aria-label="' + esc(t('mercado.f_mover_izq')) + '"' + (i === 0 ? ' disabled' : '') + '>&larr;</button>' +
        '<button type="button" data-m="1" data-i="' + i + '" aria-label="' + esc(t('mercado.f_mover_der')) + '"' + (i === fotos.length - 1 ? ' disabled' : '') + '>&rarr;</button>' +
        '<button type="button" data-x="' + i + '" aria-label="' + esc(t('mercado.f_quitar')) + '">&times;</button></div></li>';
    }).join('');
    form.querySelector('.mk-add').hidden = fotos.length >= MAX;
  }
  thumbs.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var i = +b.dataset.i;
    if (b.dataset.x !== undefined) { fotos.splice(+b.dataset.x, 1); }
    else { var j = i + (+b.dataset.m); var tmp = fotos[i]; fotos[i] = fotos[j]; fotos[j] = tmp; }
    fotosCambiaron = true; pintar();
  });
  form.querySelector('[data-files]').addEventListener('change', function (e) {
    var files = [].slice.call(e.target.files || []).slice(0, MAX - fotos.length);
    e.target.value = '';
    Promise.all(files.map(reducir)).then(function (blobs) {
      blobs.forEach(function (b) { fotos.push({ blob: b, url: URL.createObjectURL(b) }); });
      fotosCambiaron = true; pintar();
    });
  });

  // ── Editar: cargar el anuncio (y sus fotos como blobs, para poder reordenar/quitar) ──
  function cargarEdicion() {
    root.querySelector('[data-h1]').textContent = t('mercado.editar_titulo');
    root.querySelector('[data-crumb]').textContent = t('mercado.editar_titulo');
    form.querySelector('[data-submit]').textContent = t('mercado.f_guardar');
    MkCuenta.api('/anuncios/' + encodeURIComponent(editId)).then(function (r) {
      if (!r.ok) { aviso(form.querySelector('.mk-out'), r.j.detail || t('mercado.no_disponible')); return; }
      var a = r.j;
      ['titulo', 'marca', 'modelo', 'precio', 'descripcion', 'pueblo', 'entrega', 'whatsapp', 'categoria'].forEach(function (k) { if (form[k]) form[k].value = a[k] == null ? '' : a[k]; });
      form.negociable.checked = !!a.negociable;
      var c = form.querySelector('[name=condicion][value="' + a.condicion + '"]'); if (c) c.checked = true;
      form.incluye.value = (a.incluye || []).join('\n'); form.falta.value = (a.falta || []).join('\n');
      llenarSub(a.subcategoria);
      Promise.all(a.fotos.map(function (u) { return fetch(u).then(function (x) { return x.blob(); }); })).then(function (bs) {
        fotos = bs.map(function (b) { return { blob: b, url: URL.createObjectURL(b) }; }); fotosCambiaron = false; pintar();
      });
    });
  }

  // ── Enviar ──
  function datos() {
    var lineas = function (v) { return v.split('\n').map(function (x) { return x.trim(); }).filter(Boolean); };
    var c = form.querySelector('[name=condicion]:checked');
    return {
      titulo: form.titulo.value.trim(), categoria: form.categoria.value, subcategoria: form.subcategoria.value || '',
      marca: form.marca.value.trim(), modelo: form.modelo.value.trim(), condicion: c ? c.value : '',
      precio: form.precio.value === '' ? null : Number(form.precio.value), negociable: form.negociable.checked,
      descripcion: form.descripcion.value.trim(), incluye: lineas(form.incluye.value), falta: lineas(form.falta.value),
      pueblo: form.pueblo.value, entrega: form.entrega.value, whatsapp: form.whatsapp.value.trim(),
    };
  }
  function validar(d) {
    if (!fotos.length) return t('mercado.f_falta_foto');
    if (fotos.length > MAX) return t('mercado.f_max_fotos');
    if (!form.checkValidity() || !d.condicion || d.precio === null) {
      var bad = form.querySelector(':invalid'); if (bad) bad.focus();
      return t('mercado.error_datos');
    }
    if (d.whatsapp && d.whatsapp.replace(/\D/g, '').replace(/^1(?=\d{10}$)/, '').length !== 10) { form.whatsapp.focus(); return t('mercado.error_datos'); }
    return '';
  }
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var out = form.querySelector('.mk-out'), btn = form.querySelector('[data-submit]');
    var d = datos(), err = validar(d);
    if (err) return aviso(out, err);
    if (!MkCuenta.sesion()) { login.hidden = false; form.hidden = true; return; }
    btn.disabled = true; aviso(out, ''); btn.textContent = t(editId ? 'mercado.f_guardando' : 'mercado.f_publicando');
    var fin = function (r, id) {
      btn.disabled = false; btn.textContent = t(editId ? 'mercado.f_guardar' : 'mercado.f_publicar');
      if (!r.ok) { if (r.status === 401) { login.hidden = false; form.hidden = true; } return aviso(out, typeof r.j.detail === 'string' ? r.j.detail : t('mercado.error_datos')); }
      var url = pref + '/mercado/a/' + id + '/';
      out.innerHTML = esc(t(editId ? 'mercado.f_guardado' : 'mercado.f_publicado')) + ' <a href="' + url + '">' + esc(t('comun.ver')) + '</a> · <a href="' + pref + '/mercado/mis-anuncios/">' + esc(t('mercado.mis_anuncios')) + '</a><br><small>' + esc(t('mercado.f_pagina_pronto')) + '</small>';
      out.hidden = false; out.dataset.ok = '1';
      if (!editId) { form.reset(); fotos = []; pintar(); llenarSub(''); }
      out.scrollIntoView({ block: 'center', behavior: 'smooth' });
    };
    var fd = function () { var x = new FormData(); fotos.forEach(function (f, i) { x.append('fotos', f.blob, 'foto' + (i + 1) + '.jpg'); }); return x; };
    if (!editId) {
      var body = fd(); body.append('datos', JSON.stringify(d));
      MkCuenta.api('/anuncios', { method: 'POST', body: body }).then(function (r) { fin(r, r.j.id); });
    } else {
      MkCuenta.api('/anuncios/' + encodeURIComponent(editId), { method: 'PATCH', json: d }).then(function (r) {
        if (!r.ok || !fotosCambiaron) return fin(r, editId);
        MkCuenta.api('/anuncios/' + encodeURIComponent(editId) + '/fotos', { method: 'PUT', body: fd() }).then(function (r2) { fotosCambiaron = !r2.ok; fin(r2, editId); });
      });
    }
  });

  pintar();
  mostrar();
})();
