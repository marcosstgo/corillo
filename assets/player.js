/* ── PLAYER SHARED JS — loaded by all individual channel pages ── */

// Globals needed by chat.js (which runs synchronously after this file)
window.$ = (s, el = document) => el.querySelector(s);
window.channel = (location.pathname.replace(/^\/|\/$/g, '').split('/')[0]
  || new URLSearchParams(location.search).get('ch') || 'katatonia').trim();

(function () {
  "use strict";

  // ================================
  // Constants
  // ================================
  const RECONNECT_DELAYS = { FAST: 1200, BASE: 1200, MAX: 30000, BACKOFF_FACTOR: 1.8 };
  const MAX_RETRIES_BEFORE_OFFLINE = 4;
  const KICK_BANNER_DURATION  = 20000;   // ms
  const KICK_MAX_AGE          = 300;     // seconds
  const STATS_INTERVAL        = 1000;    // ms
  const WATCH_INTERVAL        = 15000;   // ms
  const STALL_CHECK_INTERVAL  = 5000;    // ms

  // ================================
  // DOM References (cached once)
  // ================================
  const $ = (s, el = document) => el.querySelector(s);
  const DOM = {
    video:            $('#video'),
    ctrlBar:          $('#ctrlBar'),
    playerWrap:       $('.playerWrap'),
    liveDot:          $('#liveDot'),
    liveTxt:          $('#liveTxt'),
    overlay:          $('#overlay'),
    ovTitle:          $('#ovTitle'),
    ovMsg:            $('#ovMsg'),
    ovRetry:          $('#ovRetry'),
    unmuteBtn:        $('#unmuteBtn'),
    chTag:            $('#chTag'),
    twitchLink:       $('#twitchLink'),
    chatChannelLabel: $('#chatChannelLabel'),
    hlsTxt:           $('#hlsTxt'),
    sRetries:         $('#sRetries'),
    retryTxt:         $('#retryTxt'),
    sBitrate:         $('#sBitrate'),
    sBuffer:          $('#sBuffer'),
    sLatency:         $('#sLatency'),
    sLevel:           $('#sLevel'),
    btnH:             $('#btnH'),
    btnV:             $('#btnV'),
    btnThemeOg:       $('#btnThemeOg'),
    btnThemeTm:       $('#btnThemeTm'),
    btnThemeTw:       $('#btnThemeTw'),
    ctrlPlay:         $('#ctrlPlay'),
    ctrlMute:         $('#ctrlMute'),
    ctrlVol:          $('#ctrlVol'),
    ctrlFs:           $('#ctrlFs'),
    themeBtn:         $('#themeBtn'),
    statsRow:         $('#statsRow'),
  };

  // ================================
  // App State
  // ================================
  const App = {
    channel:  '',
    twitchUser: '',
    mode:     'horizontal',
    // Player
    hls:      null,
    rtcPc:    null,
    retries:  0,
    retryTimer:      null,
    watchTimer:      null,
    statsTimer:      null,
    kickBannerTimer: null,
    ctrlTimer:       null,
    wakeLock:        null,
    // FIX #1: separate controller for per-session video listeners only.
    // Permanent UI listeners (buttons, controls) live in initAc and are never aborted.
    sessionAc: null,
    // Flags
    useWebRTC:             false,
    unmuteAttemptPending:  false,
    // HLS stats
    emaBitrate:  null,
    hookedHls:   false,
    // Offline thumb
    offlineThumb: null,
    thumbReady:   false,
    // Volume
    volume: 1,
    muted:  true,
  };

  // ================================
  // Helpers
  // ================================

  function getRetryDelay(retries) {
    if (retries <= MAX_RETRIES_BEFORE_OFFLINE) return RECONNECT_DELAYS.FAST;
    return Math.min(
      RECONNECT_DELAYS.MAX,
      RECONNECT_DELAYS.BASE * Math.pow(RECONNECT_DELAYS.BACKOFF_FACTOR, Math.min(retries - MAX_RETRIES_BEFORE_OFFLINE, 9))
    );
  }

  function formatBitrate(bps) {
    if (!bps || !isFinite(bps) || bps <= 0) return '—';
    return (bps / 1_000_000).toFixed(1) + ' Mbps';
  }

  function isMobile() {
    return window.matchMedia('(hover: none) and (pointer: coarse)').matches;
  }

  // ================================
  // UI
  // ================================

  function setLive(on) {
    DOM.liveDot.className   = 'dot' + (on ? ' on' : '');
    DOM.liveTxt.textContent = on ? 'en vivo' : 'offline';
  }

  function showOverlay(title, msg) {
    hideUnmuteBanner();
    DOM.ovTitle.textContent = title;
    DOM.ovMsg.textContent   = msg;
    DOM.overlay.classList.add('show');
    if (App.thumbReady) App.offlineThumb.classList.add('visible');
  }

  function hideOverlay() {
    DOM.overlay.classList.remove('show');
    if (App.offlineThumb) App.offlineThumb.classList.remove('visible');
  }

  function showUnmuteBanner() {
    if (!DOM.video.muted) return;
    if (!isMobile() && localStorage.getItem('corillo_muted') === 'false') {
      if (App.unmuteAttemptPending) return;
      App.unmuteAttemptPending = true;
      const onPause = () => {
        DOM.video.removeEventListener('pause', onPause);
        DOM.video.muted = true;
        DOM.unmuteBtn.classList.add('show');
      };
      DOM.video.addEventListener('pause', onPause);
      DOM.video.muted = false;
      setTimeout(() => { DOM.video.removeEventListener('pause', onPause); App.unmuteAttemptPending = false; }, 1000);
    } else {
      DOM.unmuteBtn.classList.add('show');
    }
  }

  function hideUnmuteBanner() { DOM.unmuteBtn.classList.remove('show'); }

  function setMode(m) {
    App.mode = m;
    DOM.video.className = m;
    DOM.btnH.classList.toggle('active', m === 'horizontal');
    DOM.btnV.classList.toggle('active', m === 'vertical');
    const url = new URL(location.href);
    if (m === 'vertical') url.searchParams.set('mode', 'vertical');
    else url.searchParams.delete('mode');
    history.replaceState(null, '', url.toString());
    startPlayer();
  }

  function setTheme(name) {
    document.body.classList.remove('theme-terminal', 'theme-twitch');
    if (name !== 'original') document.body.classList.add('theme-' + name);
    localStorage.setItem('corillo_theme', name);
    DOM.btnThemeOg.classList.toggle('active', name === 'original');
    DOM.btnThemeTm.classList.toggle('active', name === 'terminal');
    DOM.btnThemeTw.classList.toggle('active', name === 'twitch');
  }

  function toggleGrain() {
    const nowOff = document.body.classList.toggle('no-grain');
    localStorage.setItem('corillo_grain', nowOff ? 'off' : 'on');
    const btn = $('#grainBtn');
    if (btn) {
      btn.style.opacity = nowOff ? '.35' : '';
      btn.title = nowOff ? 'Activar efecto de grano' : 'Desactivar efecto de grano';
    }
  }

  function toggleWebRTC() {
    App.useWebRTC = !App.useWebRTC;
    const btn = $('#ctrlRtc');
    if (btn) {
      btn.style.opacity = App.useWebRTC ? '1' : '.4';
      btn.style.color   = App.useWebRTC ? '#00D4FF' : '';
      btn.title = App.useWebRTC ? 'Cambiar a HLS' : 'Activar WebRTC (latencia baja ~200ms)';
    }
    App.retries = 0;
    startPlayer();
  }

  function syncVolume() {
    const v = DOM.video;
    App.volume = v.volume;
    App.muted  = v.muted;
    DOM.ctrlVol.value = v.muted ? 0 : v.volume;
    const icon = DOM.ctrlMute.querySelector('i');
    if      (v.muted || v.volume === 0) icon.className = 'fa-solid fa-volume-xmark';
    else if (v.volume < 0.5)            icon.className = 'fa-solid fa-volume-low';
    else                                icon.className = 'fa-solid fa-volume-high';
  }

  function isFullscreen() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }

  function updateFsIcon() {
    DOM.ctrlFs.querySelector('i').className = isFullscreen() ? 'fa-solid fa-compress' : 'fa-solid fa-expand';
  }

  function showControls() {
    DOM.ctrlBar.classList.add('visible');
    clearTimeout(App.ctrlTimer);
    App.ctrlTimer = setTimeout(() => DOM.ctrlBar.classList.remove('visible'), 3000);
  }

  // ================================
  // Kick Banner
  // ================================

  function checkKickBanner() {
    fetch('/assets/kick/' + App.channel + '.json?t=' + Date.now(), { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(kick => {
        if (!kick || (Date.now() / 1000 - kick.ts) >= KICK_MAX_AGE) return;
        const banner = $('#kickBanner');
        if (!banner) return;
        banner.textContent =
          '⛔ Stream desconectado por bitrate alto (' + kick.kbps.toLocaleString() + ' Kbps). ' +
          'Si eres el streamer y aún no lo corregiste: configura 4,000–4,500 Kbps en OBS / Meld Studio. ' +
          '(Toca para cerrar)';
        banner.style.display = 'block';
        clearTimeout(App.kickBannerTimer);
        App.kickBannerTimer = setTimeout(() => { banner.style.display = 'none'; }, KICK_BANNER_DURATION);
      })
      .catch(() => {});
  }

  // ================================
  // Wake Lock
  // ================================

  async function requestWakeLock() {
    if (!('wakeLock' in navigator)) return;
    try {
      App.wakeLock = await navigator.wakeLock.request('screen');
      App.wakeLock.addEventListener('release', () => { App.wakeLock = null; });
    } catch {}
  }

  function releaseWakeLock() {
    if (App.wakeLock) { App.wakeLock.release(); App.wakeLock = null; }
  }

  // ================================
  // Stats
  // ================================

  function startStatsPolling() {
    if (App.statsTimer) return;

    // Hook FRAG_LOADED once per HLS session for bitrate EMA
    if (!App.hookedHls && window.Hls && App.hls) {
      App.hookedHls = true;
      App.hls.on(Hls.Events.FRAG_LOADED, (_, data) => {
        try {
          const bytes = data?.stats?.loaded || 0;
          const dur   = data?.frag?.duration || 0;
          if (bytes > 0 && dur > 0) {
            const bps = (bytes * 8) / dur;
            App.emaBitrate = App.emaBitrate == null ? bps : App.emaBitrate * .75 + bps * .25;
          }
        } catch {}
      });
    }

    const v = DOM.video;
    App.statsTimer = setInterval(() => {
      if (!v) return;
      if (v.readyState >= 2 && v.buffered.length) {
        const buf = v.buffered.end(v.buffered.length - 1) - v.currentTime;
        DOM.sBuffer.textContent = isFinite(buf) ? buf.toFixed(1) + 's' : '—';
      }
      if (v.seekable?.length > 0) {
        const lat = v.seekable.end(v.seekable.length - 1) - v.currentTime;
        DOM.sLatency.textContent = (isFinite(lat) && lat >= 0) ? lat.toFixed(1) + 's' : '—';
      }
      const w = v.videoWidth, h = v.videoHeight;
      DOM.sLevel.textContent   = (w > 0 && h > 0) ? `${w}×${h}` : '—';
      DOM.sBitrate.textContent = formatBitrate(App.emaBitrate);
    }, STATS_INTERVAL);
  }

  function stopStatsPolling() {
    clearInterval(App.statsTimer);
    App.statsTimer  = null;
    App.emaBitrate  = null;
    App.hookedHls   = false;
    ['sBitrate','sBuffer','sLatency','sLevel'].forEach(id => DOM[id].textContent = '—');
  }

  // ================================
  // Watch Mode
  // ================================

  function stopWatch() {
    if (App.watchTimer) { clearInterval(App.watchTimer); App.watchTimer = null; }
  }

  function startWatch() {
    stopWatch();
    showOverlay('Sin transmisión', 'El canal no está en vivo ahora mismo.');
    App.watchTimer = setInterval(async () => {
      try {
        const r    = await fetch('/mediamtx-api/v3/paths/list', { cache: 'no-store' });
        const data = await r.json();
        const live = (data.items || []).find(p => p.name === 'live/' + App.channel && p.ready);
        if (live) { stopWatch(); App.retries = 0; startPlayer(); }
      } catch {}
    }, WATCH_INTERVAL);
  }

  // ================================
  // Cleanup
  // ================================

  function cleanup() {
    stopWatch();
    stopStatsPolling();
    if (App.retryTimer)      { clearTimeout(App.retryTimer);      App.retryTimer      = null; }
    if (App.kickBannerTimer) { clearTimeout(App.kickBannerTimer); App.kickBannerTimer = null; }

    // FIX #1: only abort per-session listeners, never the permanent UI listeners from init()
    if (App.sessionAc) { App.sessionAc.abort(); App.sessionAc = null; }

    if (App.hls) {
      try { App.hls.destroy(); } catch {}
      App.hls = null;
      window._hlsInstance = null;
    }
    if (App.rtcPc) {
      try { App.rtcPc.close(); } catch {}
      App.rtcPc = null;
    }

    const v = DOM.video;
    if (v) {
      try { v.pause(); } catch {}
      if (v.srcObject) { v.srcObject.getTracks().forEach(t => t.stop()); v.srcObject = null; }
      v.removeAttribute('src');
      v.load();
    }

    App.unmuteAttemptPending = false;
    setLive(false);
  }

  // ================================
  // Native HLS — Safari
  // ================================

  function setupNativeHLS(url) {
    const v = DOM.video;
    v.src = url;

    // FIX #1: use sessionAc for session-specific listeners only
    const sessionAc = new AbortController();
    App.sessionAc = sessionAc;

    v.addEventListener('error', () => scheduleRetry('Error de HLS nativo'), { signal: sessionAc.signal, once: true });

    // FIX #2: start stall watcher only after 'playing' fires — avoids false positives during initial buffering
    let stallTimer = null;
    let lastTime   = -1;

    function startStallWatch() {
      lastTime   = DOM.video.currentTime;
      stallTimer = setInterval(() => {
        if (!v.paused && v.currentTime === lastTime) {
          clearInterval(stallTimer);
          scheduleRetry('stall nativo');
        }
        lastTime = v.currentTime;
      }, STALL_CHECK_INTERVAL);
    }

    function stopStallWatch() { clearInterval(stallTimer); stallTimer = null; }

    v.addEventListener('playing', startStallWatch,  { signal: sessionAc.signal, once: true });
    v.addEventListener('pause',   stopStallWatch,   { signal: sessionAc.signal });
    v.addEventListener('ended',   stopStallWatch,   { signal: sessionAc.signal });

    v.play()
      .then(() => { hideOverlay(); setLive(true); startStatsPolling(); showUnmuteBanner(); })
      .catch(e => {
        if (e?.name === 'NotAllowedError') showOverlay('Toca para reproducir', 'Presiona el botón para iniciar el stream.');
        else scheduleRetry('Error al reproducir nativo');
      });
  }

  // ================================
  // HLS.js
  // ================================

  function setupHlsJs(url) {
    const hls = new Hls({
      lowLatencyMode:          false,
      liveSyncDurationCount:   3,     // 3 × 2s = 6s behind live edge — stable with mpegts
      backBufferLength:        8,
      maxBufferLength:         12,
      maxLiveSyncPlaybackRate: 1.1,
      manifestLoadingMaxRetry: 1,
      fragLoadingMaxRetry:     2,
    });
    App.hls = hls;
    window._hlsInstance = hls;

    hls.on(Hls.Events.MEDIA_ATTACHED, () => hls.loadSource(url));
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      DOM.video.play()
        .then(() => { hideOverlay(); setLive(true); startStatsPolling(); showUnmuteBanner(); })
        .catch(() => { showOverlay('Toca para reproducir', 'Presiona el botón para iniciar el stream.'); });
    });
    hls.on(Hls.Events.ERROR, (_, d) => {
      if (!d) return;
      if (d.fatal) { cleanup(); scheduleRetry(d.type || 'Error fatal'); return; }
      if (d.details === Hls.ErrorDetails.BUFFER_STALLED_ERROR) { try { hls.recoverMediaError(); } catch {} }
    });
    hls.attachMedia(DOM.video);
  }

  // ================================
  // WebRTC — WHEP
  // ================================

  async function startWebRTC() {
    cleanup();
    showOverlay('Cargando', 'Conectando (WebRTC)…');
    DOM.hlsTxt.textContent = '⚡ RTC';
    DOM.video.muted = true;

    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    App.rtcPc = pc;
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' });
    pc.ontrack = (e) => {
      if (!DOM.video.srcObject) DOM.video.srcObject = new MediaStream();
      DOM.video.srcObject.addTrack(e.track);
    };
    pc.onconnectionstatechange = () => {
      const s = pc.connectionState;
      if (s === 'failed' || s === 'disconnected') scheduleRetry('WebRTC disconnected');
    };

    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await Promise.race([
        new Promise(resolve => {
          if (pc.iceGatheringState === 'complete') { resolve(); return; }
          pc.addEventListener('icegatheringstatechange', function onState() {
            if (pc.iceGatheringState === 'complete') {
              pc.removeEventListener('icegatheringstatechange', onState);
              resolve();
            }
          });
        }),
        new Promise(resolve => setTimeout(resolve, 4000)),
      ]);

      const whepUrl = '/webrtc/live/' + encodeURIComponent(App.channel) + '/whep';
      const resp = await fetch(whepUrl, { method: 'POST', headers: { 'Content-Type': 'application/sdp' }, body: pc.localDescription.sdp });
      if (!resp.ok) throw new Error('WHEP response not OK');
      await pc.setRemoteDescription({ type: 'answer', sdp: await resp.text() });

      // FIX #3: separate try/catch for play() — NotAllowedError shows overlay, not retry
      try {
        await DOM.video.play();
        hideOverlay(); setLive(true); showUnmuteBanner();
      } catch (playErr) {
        if (playErr?.name === 'NotAllowedError') showOverlay('Toca para reproducir', 'Presiona el botón para iniciar el stream.');
        else scheduleRetry('WebRTC play error');
      }
    } catch {
      scheduleRetry('WebRTC error');
    }
  }

  // ================================
  // Retry Logic
  // ================================

  function scheduleRetry(reason) {
    App.retries++;
    DOM.sRetries.textContent = App.retries;
    DOM.retryTxt.textContent = App.retries;

    const delay     = getRetryDelay(App.retries);
    const isOffline = reason === 'networkError' || reason === 'Error de HLS nativo';

    fetch('/assets/kick/' + App.channel + '.json?t=' + Date.now(), { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(kick => {
        if (kick && (Date.now() / 1000 - kick.ts) < KICK_MAX_AGE) {
          showOverlay(
            'Stream pausado temporalmente',
            'El stream fue desconectado por bitrate alto (' + kick.kbps.toLocaleString() + ' Kbps). ' +
            'Si eres el streamer: configura 4,000–4,500 Kbps en OBS o Meld Studio y reconecta. ' +
            'Reintentando en ' + Math.round(delay / 1000) + 's…'
          );
          App.retryTimer = setTimeout(startPlayer, delay);
        } else if (isOffline && App.retries > MAX_RETRIES_BEFORE_OFFLINE) {
          startWatch();
        } else {
          showOverlay(
            isOffline ? 'Sin transmisión' : 'Reconectando',
            (isOffline ? 'El canal no está en vivo ahora mismo.' : 'Error de conexión.') + ' Reintentando en ' + Math.round(delay / 1000) + 's…'
          );
          App.retryTimer = setTimeout(startPlayer, delay);
        }
      })
      .catch(() => {
        if (isOffline && App.retries > MAX_RETRIES_BEFORE_OFFLINE) {
          startWatch();
        } else {
          showOverlay(
            isOffline ? 'Sin transmisión' : 'Reconectando',
            (isOffline ? 'El canal no está en vivo ahora mismo.' : 'Error de conexión.') + ' Reintentando en ' + Math.round(delay / 1000) + 's…'
          );
          App.retryTimer = setTimeout(startPlayer, delay);
        }
      });
  }

  // ================================
  // Player Entry Point
  // ================================

  function startPlayer() {
    if (App.useWebRTC) { startWebRTC(); return; }
    cleanup();
    const path = App.mode === 'vertical' ? App.channel + '-vertical' : App.channel;
    const url  = '/live/' + encodeURIComponent(path) + '/index.m3u8';
    DOM.hlsTxt.textContent = App.mode === 'vertical' ? '9:16' : '16:9';
    showOverlay('Cargando', 'Iniciando stream…');
    DOM.video.muted = true;

    if (DOM.video.canPlayType('application/vnd.apple.mpegurl')) {
      setupNativeHLS(url);
    } else if (window.Hls && Hls.isSupported()) {
      setupHlsJs(url);
    } else {
      showOverlay('No compatible', 'Este navegador no puede reproducir HLS. Usa Safari en iOS o un navegador moderno.');
    }
  }

  // ================================
  // Public Profile
  // ================================

  function buildPanel(el, p) {
    if (p.title) {
      const t = document.createElement('div');
      t.className = 'panel-title';
      t.textContent = p.title;
      el.appendChild(t);
    }
    if (p.text) {
      const d = document.createElement('div');
      d.className = 'panel-text';
      d.textContent = p.text;
      el.appendChild(d);
    }
    if (p.url) {
      const lbl = document.createElement('div');
      lbl.className = 'panel-url-lbl';
      lbl.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i>';
      el.appendChild(lbl);
    }
  }

  function loadProfile() {
    if (!DOM.statsRow) return;
    fetch('/chat-api/profile/' + App.channel)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        const hasBio    = data.bio && data.bio.trim();
        const hasLinks  = data.twitch || data.instagram || data.tiktok;
        const hasAvatar = data.avatar_url;
        if (!hasBio && !hasLinks && !hasAvatar) return;

        const sec = document.createElement('div');
        sec.className = 'profile-section';
        const label = document.createElement('div');
        label.className = 'profile-label';
        label.textContent = 'SOBRE ' + (data.display_name || App.channel).toUpperCase();
        sec.appendChild(label);

        const row = document.createElement('div');
        row.className = 'profile-row';

        if (hasAvatar) {
          const img = document.createElement('img');
          img.className = 'profile-avatar';
          img.src = data.avatar_url;
          img.alt = data.display_name || App.channel;
          row.appendChild(img);
        } else {
          const ava = document.createElement('div');
          ava.className = 'profile-avatar profile-avatar-initial';
          ava.style.background = data.color || 'var(--panel)';
          ava.textContent = (data.display_name || App.channel)[0].toUpperCase();
          row.appendChild(ava);
        }

        const info = document.createElement('div');
        info.className = 'profile-info';
        if (data.display_name) {
          const name = document.createElement('div');
          name.className = 'profile-name';
          name.textContent = data.display_name;
          info.appendChild(name);
        }
        if (hasBio) {
          const bio = document.createElement('p');
          bio.className = 'profile-bio';
          bio.textContent = data.bio.trim();
          info.appendChild(bio);
        }
        if (hasLinks) {
          const links = document.createElement('div');
          links.className = 'profile-links';
          if (data.twitch)
            links.innerHTML += `<a href="https://twitch.tv/${data.twitch}" target="_blank" rel="noopener"><i class="fa-brands fa-twitch"></i><span>Twitch</span></a>`;
          if (data.instagram)
            links.innerHTML += `<a href="https://instagram.com/${data.instagram}" target="_blank" rel="noopener"><i class="fa-brands fa-instagram"></i><span>Instagram</span></a>`;
          if (data.tiktok)
            links.innerHTML += `<a href="https://tiktok.com/@${data.tiktok}" target="_blank" rel="noopener"><i class="fa-brands fa-tiktok"></i><span>TikTok</span></a>`;
          info.appendChild(links);
        }
        row.appendChild(info);
        sec.appendChild(row);
        DOM.statsRow.after(sec);

        const panels = Array.isArray(data.panels) ? data.panels.filter(p => p && p.title) : [];
        if (panels.length) {
          const grid = document.createElement('div');
          grid.className = 'panels-grid';
          panels.forEach(p => {
            const card = document.createElement('div');
            card.className = 'panel-card';
            if (p.url) {
              const a = document.createElement('a');
              a.href = p.url; a.target = '_blank'; a.rel = 'noopener'; a.className = 'panel-link';
              buildPanel(a, p); card.appendChild(a);
            } else {
              buildPanel(card, p);
            }
            grid.appendChild(card);
          });
          sec.after(grid);
        }
      })
      .catch(() => {});
  }

  // ================================
  // Init — runs once, permanent listeners never removed
  // ================================

  function init() {
    // Channel (already set as window.channel before IIFE for chat.js)
    App.channel = window.channel;
    const TWITCH_MAP = { katatonia: 'katat0nia' };
    App.twitchUser = TWITCH_MAP[App.channel] || App.channel;

    // Meta tags
    const chUpper  = App.channel.toUpperCase();
    const thumbUrl = 'https://corillo.live/assets/thumbs/' + App.channel + '.jpg';
    const pageUrl  = 'https://corillo.live/' + App.channel + '/';
    const desc     = 'Stream en vivo de ' + chUpper + ' en CORILLO — plataforma independiente desde Puerto Rico.';
    document.title = 'CORILLO — ' + chUpper;
    [['og:title','CORILLO — '+chUpper],['og:url',pageUrl],['og:description',desc],['og:image',thumbUrl],
     ['twitter:title','CORILLO — '+chUpper],['twitter:description',desc],['twitter:image',thumbUrl]]
      .forEach(([prop, val]) => {
        const el = document.querySelector(`meta[property="${prop}"],meta[name="${prop}"]`);
        if (el) el.setAttribute('content', val);
      });
    if (DOM.chTag)            DOM.chTag.textContent            = '— ' + chUpper;
    if (DOM.twitchLink)       DOM.twitchLink.href              = 'https://twitch.tv/' + App.twitchUser;
    if (DOM.chatChannelLabel) DOM.chatChannelLabel.textContent = App.twitchUser;

    // Offline thumbnail
    App.offlineThumb = document.createElement('img');
    App.offlineThumb.className = 'offline-thumb';
    App.offlineThumb.onload = () => {
      App.thumbReady = true;
      if (DOM.overlay.classList.contains('show')) App.offlineThumb.classList.add('visible');
    };
    App.offlineThumb.src = '/assets/thumbs/' + App.channel + '.jpg';
    DOM.playerWrap.insertBefore(App.offlineThumb, DOM.playerWrap.firstChild);

    // Kick banner
    const kickBanner = document.createElement('div');
    kickBanner.id = 'kickBanner';
    kickBanner.style.cssText = [
      'display:none','position:absolute','bottom:56px','left:50%','transform:translateX(-50%)',
      'background:rgba(180,30,30,.92)','color:#fff','padding:10px 18px','border-radius:8px',
      'font-size:.82rem','text-align:center','z-index:50','max-width:92%','cursor:pointer',
      'box-shadow:0 2px 12px rgba(0,0,0,.5)','line-height:1.4',
    ].join(';');
    kickBanner.addEventListener('click', () => { kickBanner.style.display = 'none'; });
    DOM.playerWrap.appendChild(kickBanner);

    // Mode
    App.mode = (new URLSearchParams(location.search).get('mode') || 'horizontal').trim();
    DOM.video.className = App.mode;
    DOM.btnH.classList.toggle('active', App.mode === 'horizontal');
    DOM.btnV.classList.toggle('active', App.mode === 'vertical');

    // Theme
    setTheme(localStorage.getItem('corillo_theme') || 'original');

    // Grain toggle button
    const grainOff = localStorage.getItem('corillo_grain') === 'off';
    if (grainOff) document.body.classList.add('no-grain');
    const grainBtn = document.createElement('button');
    grainBtn.id = 'grainBtn';
    grainBtn.className = 'theme-btn';
    grainBtn.title = grainOff ? 'Activar efecto de grano' : 'Desactivar efecto de grano';
    grainBtn.innerHTML = '&#9641;';
    grainBtn.style.fontSize = '.65rem';
    if (grainOff) grainBtn.style.opacity = '.35';
    DOM.themeBtn.parentNode.insertBefore(grainBtn, DOM.themeBtn.nextSibling);
    grainBtn.addEventListener('click', toggleGrain);

    // WebRTC toggle button
    const pill   = DOM.hlsTxt.closest('.pill') || DOM.hlsTxt.parentElement;
    const rtcBtn = document.createElement('button');
    rtcBtn.id = 'ctrlRtc';
    rtcBtn.className = 'ctrl-btn';
    rtcBtn.title = 'Activar WebRTC (latencia baja ~200ms)';
    rtcBtn.innerHTML = '<i class="fa-solid fa-bolt"></i>';
    rtcBtn.style.cssText = 'opacity:.4;font-size:.8rem';
    pill.after(rtcBtn);
    rtcBtn.addEventListener('click', toggleWebRTC);

    // Volume from storage
    const savedVol = parseFloat(localStorage.getItem('corillo_volume'));
    if (!isNaN(savedVol)) { DOM.video.volume = savedVol; App.volume = savedVol; }
    DOM.ctrlVol.value = DOM.video.volume;
    syncVolume();

    // ── Permanent event listeners — never removed ──────────────────

    // Mode / theme
    DOM.btnH.addEventListener('click', () => setMode('horizontal'));
    DOM.btnV.addEventListener('click', () => setMode('vertical'));
    DOM.btnThemeOg.addEventListener('click', () => setTheme('original'));
    DOM.btnThemeTm.addEventListener('click', () => setTheme('terminal'));
    DOM.btnThemeTw.addEventListener('click', () => setTheme('twitch'));

    // Overlay retry
    DOM.ovRetry.addEventListener('click', () => { App.retries = 0; startPlayer(); });

    // Unmute button
    DOM.unmuteBtn.addEventListener('click', () => {
      DOM.video.muted = false;
      DOM.video.volume = App.volume || 1;
      if (DOM.video.paused) DOM.video.play().catch(() => {});
      localStorage.setItem('corillo_muted', 'false');
      hideUnmuteBanner();
    });

    // Video lifecycle
    DOM.video.addEventListener('waiting', () => setLive(false));
    DOM.video.addEventListener('playing', () => {
      setLive(true); hideOverlay(); startStatsPolling(); showUnmuteBanner(); checkKickBanner(); requestWakeLock();
    });
    DOM.video.addEventListener('pause',   releaseWakeLock);
    DOM.video.addEventListener('ended',   releaseWakeLock);
    DOM.video.addEventListener('volumechange', () => {
      syncVolume();
      localStorage.setItem('corillo_volume', App.volume);
      localStorage.setItem('corillo_muted', App.muted ? 'true' : 'false');
      if (!App.muted) hideUnmuteBanner();
    });
    DOM.video.addEventListener('play',  () => { DOM.ctrlPlay.querySelector('i').className = 'fa-solid fa-pause'; });
    DOM.video.addEventListener('pause', () => { DOM.ctrlPlay.querySelector('i').className = 'fa-solid fa-play';  });

    // Controls bar
    DOM.playerWrap.addEventListener('mousemove', showControls);
    DOM.playerWrap.addEventListener('mouseleave', () => { clearTimeout(App.ctrlTimer); DOM.ctrlBar.classList.remove('visible'); });
    DOM.playerWrap.addEventListener('touchstart', showControls, { passive: true });

    // Control buttons
    DOM.ctrlPlay.addEventListener('click', () => { if (DOM.video.paused) DOM.video.play().catch(() => {}); else DOM.video.pause(); });
    DOM.ctrlMute.addEventListener('click', () => { DOM.video.muted = !DOM.video.muted; if (!DOM.video.muted && DOM.video.volume === 0) DOM.video.volume = 1; });
    DOM.ctrlVol.addEventListener('input',  () => { DOM.video.volume = +DOM.ctrlVol.value; DOM.video.muted = DOM.video.volume === 0; });

    // Fullscreen
    DOM.ctrlFs.addEventListener('click', () => {
      if (isFullscreen()) { (document.exitFullscreen || document.webkitExitFullscreen).call(document).catch(() => {}); }
      else {
        const v = DOM.video;
        if      (v.requestFullscreen)      v.requestFullscreen().catch(() => {});
        else if (v.webkitRequestFullscreen) v.webkitRequestFullscreen();
        else if (v.webkitEnterFullscreen)   v.webkitEnterFullscreen();
      }
    });
    document.addEventListener('fullscreenchange',        updateFsIcon);
    document.addEventListener('webkitfullscreenchange',  updateFsIcon);
    DOM.video.addEventListener('webkitbeginfullscreen', () => { DOM.ctrlFs.querySelector('i').className = 'fa-solid fa-compress'; });
    DOM.video.addEventListener('webkitendfullscreen',   () => { DOM.ctrlFs.querySelector('i').className = 'fa-solid fa-expand';   });

    // Visibility / wake lock
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) releaseWakeLock();
      else if (!DOM.video.paused) requestWakeLock();
    });

    // Dark/Light theme
    if (DOM.themeBtn) {
      DOM.themeBtn.addEventListener('click', () => {
        const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('corillo-theme', next);
      });
    }
    const savedGlobalTheme = localStorage.getItem('corillo-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedGlobalTheme);

    // Profile + start
    loadProfile();
    startPlayer();
  }

  // Run
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

})();
