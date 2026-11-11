// /bf6/ (10-nov-2026): reproductor de YouTube al tocar (no carga nada de YouTube hasta entonces) y quién de Corillo
// está en vivo con Battlefield en el título.
(function () {
  const { $, esc } = window.OV;
  const ES_BF6 = /battlefield|\bbf6\b|redsec/i;

  /* reproductor: se cambia el botón por el iframe de youtube-nocookie */
  const repro = $('.b6-reproductor');
  const poner = id => {
    if (!repro || !/^[\w-]{11}$/.test(id || '')) return false;
    repro.innerHTML = `<iframe src="https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0" title="Video de YouTube" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>`;
    repro.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return true;
  };
  if (repro) repro.addEventListener('click', () => poner(repro.dataset.video), { once: true });
  document.querySelectorAll('.b6-canal .b6-video').forEach(a => a.addEventListener('click', e => {
    if (e.metaKey || e.ctrlKey || e.shiftKey) return;
    if (poner(a.dataset.video)) e.preventDefault();
  }));

  /* en vivo en Corillo */
  const caja = $('#b6Vivo');
  async function vivos() {
    try {
      const [paths, streamers] = await Promise.all([
        fetch('https://media.corillo.live/mediamtx-api/v3/paths/list', { signal: AbortSignal.timeout(6000) }).then(r => r.json()),
        fetch('https://api.corillo.live/api/streamers', { signal: AbortSignal.timeout(6000) }).then(r => r.json()),
      ]);
      const en = new Set((paths.items || []).filter(p => p.ready).map(p => p.name.replace('live/', '')));
      const lista = (streamers || []).filter(s => en.has(s.key) && ES_BF6.test(s.stream_title || ''));
      caja.hidden = !lista.length;
      caja.innerHTML = lista.map(s => `<a class="b6-vivo" href="/${encodeURIComponent(s.key)}/">${/^https:\/\//.test(s.avatar_url || '') ? `<img src="${esc(s.avatar_url)}" alt="">` : `<span class="b6-ava">${esc((s.name || '?')[0])}</span>`}
        <span><b>${esc(s.name)} · en vivo</b><span>${esc(s.stream_title)}</span></span></a>`).join('');
    } catch (e) { /* si no contesta, la sección sigue con los videos */ }
  }
  if (caja) { vivos(); setInterval(vivos, 60000); }
})();
