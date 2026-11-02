/* /eventos/: los días que faltan se recalculan en el navegador (la página solo se reconstruye una vez al día). */
(function () {
  var hoy = new Date(Date.now() - 4 * 3600 * 1000).toISOString().slice(0, 10);   // Puerto Rico: AST todo el año
  var dias = function (a, b) { return Math.round((Date.parse(b) - Date.parse(a)) / 86400000); };
  document.querySelectorAll('[data-faltan]').forEach(function (el) {
    var ini = el.getAttribute('data-faltan'), fin = el.getAttribute('data-fin') || ini, n = dias(hoy, ini);
    el.textContent = n > 1 ? 'Faltan ' + n + ' días' : n === 1 ? 'Mañana' : hoy <= fin ? 'Hoy' : 'Ya pasó';
  });
  document.querySelectorAll('[data-fecha]').forEach(function (el) {
    var f = el.getAttribute('data-fecha');
    el.classList.toggle('es-hoy', f === hoy);
    el.classList.toggle('ya-paso', f < hoy);
    if (f === hoy) el.setAttribute('aria-current', 'date');
  });
  document.querySelectorAll('[data-compartir]').forEach(function (b) {
    b.addEventListener('click', async function () {
      var url = b.getAttribute('data-compartir'), titulo = b.getAttribute('data-titulo') || document.title;
      try {
        if (navigator.share) { await navigator.share({ title: titulo, url: url }); return; }
        await navigator.clipboard.writeText(url);
        var s = b.querySelector('span'); if (s) { s.textContent = 'Enlace copiado'; setTimeout(function () { s.textContent = 'Compartir'; }, 2000); }
      } catch (e) {}
    });
  });
})();
