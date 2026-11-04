// Modo cine (3-nov-2026): agranda el video en el canal y en /vods/v/. Botón [data-cine] o tecla T; se recuerda entre visitas.
// Carga en el <head> para que la clase esté puesta antes de pintar y el video no brinque.
// Solo cambia el CSS: el <video> no se mueve de sitio, así que no se corta ni vuelve a cargar.
(function () {
  const CLAVE = 'corillo_cine';
  const raiz = document.documentElement;
  // En /vods/v/ el menú lateral se recoge a íconos para dar espacio; al salir vuelve a como lo tenía la persona (misma regla que SiteShell).
  function menu(on) {
    let m = null;
    try { m = localStorage.getItem('corillo-sb'); } catch {}
    raiz.classList.toggle('nv-min', on || m === 'min' || (m !== 'open' && innerWidth < 1360));
  }
  try { if (localStorage.getItem(CLAVE) === '1') { raiz.classList.add('modo-cine'); menu(true); } } catch {}

  const activo = () => raiz.classList.contains('modo-cine');
  // El CSS esconde el botón donde no aplica (celular, 9:16, canal apagado): la tecla obedece lo mismo.
  const hayBoton = () => [...document.querySelectorAll('[data-cine]')].some(b => b.offsetParent !== null);

  function pintar() {
    const texto = activo() ? 'Vista normal' : 'Modo cine';
    document.querySelectorAll('[data-cine]').forEach(b => {
      b.setAttribute('aria-pressed', String(activo()));
      b.setAttribute('aria-label', texto);
      const t = b.querySelector('.cine-txt');
      if (t) t.textContent = texto;
    });
  }

  function alternar() {
    raiz.classList.toggle('modo-cine');
    menu(activo());
    try { localStorage.setItem(CLAVE, activo() ? '1' : '0'); } catch {}
    pintar();
  }

  document.addEventListener('click', e => { if (e.target.closest?.('[data-cine]')) alternar(); });
  document.addEventListener('keydown', e => {
    if (e.key.toLowerCase() !== 't' || e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    // Sin esto, escribir una «t» en el chat cambiaría el modo.
    if (e.target.closest?.('input, textarea, select, [contenteditable]')) return;
    if (document.fullscreenElement || document.webkitFullscreenElement || !hayBoton()) return;
    alternar();
  });

  window.pintarModoCine = pintar; // /vods/v/ crea su botón después de cargar el video
  document.addEventListener('DOMContentLoaded', pintar);
})();
