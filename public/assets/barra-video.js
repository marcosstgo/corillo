// Barra de controles propia para /vods/v/ en computadora (3-nov-2026): la del navegador no admite botones nuevos y Marcos quiere
// el modo cine abajo a la derecha, con los demás controles. En pantallas táctiles sigue la del navegador (iOS la necesita).
window.barraVideo = function (video) {
  const wrap = video.closest('.player-wrap');
  const compu = matchMedia('(min-width:961px) and (hover:hover) and (pointer:fine)');
  const ico = (n) => `<i class="fa-solid fa-${n}" aria-hidden="true"></i>`;
  const hora = (s) => {
    s = Math.max(0, Math.floor(s || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = String(s % 60).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${x}` : `${m}:${x}`;
  };

  const bar = document.createElement('div');
  bar.className = 'barra-video';
  bar.innerHTML = `
    <div class="bv-linea"><span class="bv-punta" hidden></span><input class="bv-avance" type="range" min="0" max="1000" step="1" value="0" aria-label="Avance del video"></div>
    <div class="bv-fila">
      <button type="button" class="bv-btn bv-play" aria-label="Reproducir">${ico('play')}</button>
      <button type="button" class="bv-btn bv-mudo" aria-label="Silenciar">${ico('volume-high')}</button>
      <input class="bv-vol" type="range" min="0" max="1" step="0.05" value="1" aria-label="Volumen">
      <span class="bv-tiempo">0:00 / 0:00</span>
      <span class="bv-espacio"></span>
      <button type="button" class="bv-btn bv-vel" aria-label="Velocidad" title="Velocidad">1x</button>
      <button type="button" class="bv-btn bv-pip" aria-label="Ventana flotante" title="Ventana flotante" hidden>${ico('clone')}</button>
      <span class="bv-cine"></span>
      <button type="button" class="bv-btn bv-fs" aria-label="Pantalla completa" title="Pantalla completa">${ico('expand')}</button>
    </div>`;
  wrap.appendChild(bar);
  const $ = (s) => bar.querySelector(s);
  const avance = $('.bv-avance'), vol = $('.bv-vol'), tiempo = $('.bv-tiempo'), punta = $('.bv-punta');
  const original = wrap.querySelector(':scope > [data-cine]');
  const cine = original.cloneNode(true);
  cine.classList.add('bv-btn');
  $('.bv-cine').replaceWith(cine);
  window.pintarModoCine?.();

  // ── pintar ──
  const dur = () => (isFinite(video.duration) ? video.duration : 0);
  let arrastrando = false;
  function pintarAvance() {
    const d = dur();
    if (!arrastrando) avance.value = d ? (video.currentTime / d) * 1000 : 0;
    let cargado = 0;
    for (let i = 0; i < video.buffered.length; i++) {
      if (video.buffered.start(i) <= video.currentTime + 0.5) cargado = Math.max(cargado, video.buffered.end(i));
    }
    avance.style.setProperty('--v', `${avance.value / 10}%`);
    avance.style.setProperty('--b', `${d ? (cargado / d) * 100 : 0}%`);
    tiempo.textContent = `${hora(arrastrando ? (avance.value / 1000) * d : video.currentTime)} / ${hora(d)}`;
  }
  function pintarPlay() {
    wrap.classList.toggle('pausado', video.paused);
    $('.bv-play').innerHTML = ico(video.paused ? 'play' : 'pause');
    $('.bv-play').setAttribute('aria-label', video.paused ? 'Reproducir' : 'Pausa');
    mostrar();
  }
  function pintarVol() {
    const nivel = video.muted ? 0 : video.volume;
    vol.value = nivel;
    vol.style.setProperty('--v', `${nivel * 100}%`);
    $('.bv-mudo').innerHTML = ico(nivel === 0 ? 'volume-xmark' : nivel < 0.5 ? 'volume-low' : 'volume-high');
    $('.bv-mudo').setAttribute('aria-label', video.muted ? 'Activar sonido' : 'Silenciar');
  }
  const enPantalla = () => document.fullscreenElement === wrap || document.webkitFullscreenElement === wrap;
  function pintarFs() {
    $('.bv-fs').innerHTML = ico(enPantalla() ? 'compress' : 'expand');
    $('.bv-fs').setAttribute('aria-label', enPantalla() ? 'Salir de pantalla completa' : 'Pantalla completa');
  }

  // ── la barra se esconde sola mientras corre el video ──
  let quieto;
  function mostrar() {
    wrap.classList.add('activa');
    clearTimeout(quieto);
    if (!video.paused) quieto = setTimeout(() => wrap.classList.remove('activa'), 2500);
  }
  wrap.addEventListener('mousemove', mostrar);
  wrap.addEventListener('focusin', mostrar);
  wrap.addEventListener('mouseleave', () => { if (!video.paused) wrap.classList.remove('activa'); });

  // ── acciones ──
  const alternarPlay = () => { video.paused ? video.play().catch(() => {}) : video.pause(); };
  const alternarMudo = () => {
    video.muted = !video.muted;
    if (!video.muted && video.volume === 0) video.volume = 0.5;
    try { localStorage.setItem('corillo_muted', String(video.muted)); } catch {}
  };
  const alternarFs = () => {
    if (enPantalla()) (document.exitFullscreen || document.webkitExitFullscreen).call(document);
    else (wrap.requestFullscreen || wrap.webkitRequestFullscreen).call(wrap);
  };
  const saltar = (s) => { video.currentTime = Math.min(dur() || Infinity, Math.max(0, video.currentTime + s)); mostrar(); };

  video.addEventListener('click', () => { if (compu.matches) alternarPlay(); });
  video.addEventListener('dblclick', () => { if (compu.matches) alternarFs(); });
  $('.bv-play').addEventListener('click', alternarPlay);
  $('.bv-mudo').addEventListener('click', alternarMudo);
  $('.bv-fs').addEventListener('click', alternarFs);
  vol.addEventListener('input', () => {
    video.volume = +vol.value;
    video.muted = video.volume === 0;
    try { localStorage.setItem('corillo_volume', video.volume); localStorage.setItem('corillo_muted', String(video.muted)); } catch {}
  });
  // Sin soltar el foco, las flechas y el espacio seguirían moviendo la barrita en vez de mandar sobre el video.
  vol.addEventListener('change', () => vol.blur());
  avance.addEventListener('input', () => { arrastrando = true; pintarAvance(); });
  avance.addEventListener('change', () => {
    video.currentTime = (avance.value / 1000) * dur();
    arrastrando = false;
    avance.blur();
    pintarAvance();
  });
  avance.addEventListener('mousemove', (e) => {
    const r = avance.getBoundingClientRect(), x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    punta.hidden = !dur();
    punta.textContent = hora(x * dur());
    punta.style.left = `${x * 100}%`;
  });
  avance.addEventListener('mouseleave', () => { punta.hidden = true; });

  const VELOCIDADES = [1, 1.25, 1.5, 2];
  $('.bv-vel').addEventListener('click', () => {
    const v = VELOCIDADES[(VELOCIDADES.indexOf(video.playbackRate) + 1) % VELOCIDADES.length];
    video.playbackRate = video.defaultPlaybackRate = v;
    $('.bv-vel').textContent = `${v}x`;
  });
  if (document.pictureInPictureEnabled && !video.disablePictureInPicture) {
    $('.bv-pip').hidden = false;
    $('.bv-pip').addEventListener('click', () => {
      (document.pictureInPictureElement ? document.exitPictureInPicture() : video.requestPictureInPicture()).catch(() => {});
    });
  }

  // Lo que la barra del navegador hacía con el teclado, y F y M como en YouTube.
  document.addEventListener('keydown', (e) => {
    if (!compu.matches || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest?.('input, textarea, select, [contenteditable]')) return;
    const k = e.key.toLowerCase();
    if (k === ' ' || k === 'k') {
      if (k === ' ' && e.target.closest?.('button, a, summary')) return; // el espacio sobre un botón aprieta ese botón
      e.preventDefault(); alternarPlay();
    } else if (k === 'arrowleft') { e.preventDefault(); saltar(-5); }
    else if (k === 'arrowright') { e.preventDefault(); saltar(5); }
    else if (k === 'm') { alternarMudo(); mostrar(); }
    else if (k === 'f' && !e.repeat) alternarFs();
  });

  video.addEventListener('timeupdate', pintarAvance);
  video.addEventListener('progress', pintarAvance);
  video.addEventListener('durationchange', pintarAvance);
  video.addEventListener('seeking', pintarAvance);
  video.addEventListener('play', pintarPlay);
  video.addEventListener('pause', pintarPlay);
  video.addEventListener('ended', pintarPlay);
  video.addEventListener('volumechange', pintarVol);
  video.addEventListener('waiting', () => wrap.classList.add('cargando'));
  for (const ev of ['playing', 'canplay', 'seeked']) video.addEventListener(ev, () => wrap.classList.remove('cargando'));
  document.addEventListener('fullscreenchange', pintarFs);
  document.addEventListener('webkitfullscreenchange', pintarFs);

  // Si la ventana se achica por debajo de la medida, vuelve la barra del navegador.
  function elegir() {
    wrap.classList.toggle('con-barra', compu.matches);
    video.controls = !compu.matches;
  }
  compu.addEventListener('change', elegir);
  elegir(); pintarPlay(); pintarVol(); pintarAvance();
};
