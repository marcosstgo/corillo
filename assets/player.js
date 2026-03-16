/* ── PLAYER SHARED JS — loaded by all individual channel pages ── */

const $ = (s, el=document) => el.querySelector(s);

// ── CHANNEL ──
const pathParts = location.pathname.replace(/^\/|\/$/g,'').split('/');
const channel   = (pathParts[0] || new URLSearchParams(location.search).get('ch') || 'katatonia').trim();

// Twitch username map — add more as needed
const TWITCH_MAP = {
  'katatonia': 'katat0nia',
};
const twitchUser = TWITCH_MAP[channel] || channel;

// Update meta tags dinamicamente — title, OG, og:image
const _chUpper = channel.toUpperCase();
const _thumbUrl = 'https://corillo.live/assets/thumbs/' + channel + '.jpg';
const _pageUrl  = 'https://corillo.live/' + channel + '/';
const _desc     = 'Stream en vivo de ' + _chUpper + ' en CORILLO — plataforma independiente desde Puerto Rico.';
document.title = 'CORILLO — ' + _chUpper;
[['og:title','CORILLO — ' + _chUpper], ['og:url', _pageUrl], ['og:description', _desc],
 ['og:image', _thumbUrl], ['twitter:title','CORILLO — ' + _chUpper],
 ['twitter:description', _desc], ['twitter:image', _thumbUrl]]
  .forEach(([prop, val]) => {
    const el = document.querySelector(`meta[property="${prop}"],meta[name="${prop}"]`);
    if (el) el.setAttribute('content', val);
  });

$('#chTag').textContent      = '— ' + _chUpper;
$('#twitchLink').href        = 'https://twitch.tv/' + twitchUser;
if ($('#chatChannelLabel')) $('#chatChannelLabel').textContent = twitchUser;

// ── MODE ──
const params = new URLSearchParams(location.search);
let mode = (params.get('mode') || 'horizontal').trim();

function setMode(m) {
  mode = m;
  $('#video').className = m;
  $('#btnH').classList.toggle('active', m === 'horizontal');
  $('#btnV').classList.toggle('active', m === 'vertical');
  history.replaceState(null,'', location.pathname + (m === 'horizontal' ? '' : '?mode=vertical'));
  start();
}
$('#btnH').addEventListener('click', () => setMode('horizontal'));
$('#btnV').addEventListener('click', () => setMode('vertical'));
$('#video').className = mode;
$('#btn' + (mode === 'vertical' ? 'V' : 'H')).classList.add('active');

// ── PLAYER THEME ──
function setTheme(name) {
  document.body.classList.remove('theme-terminal','theme-twitch');
  if (name !== 'original') document.body.classList.add('theme-' + name);
  localStorage.setItem('corillo_theme', name);
  $('#btnThemeOg').classList.toggle('active', name === 'original');
  $('#btnThemeTm').classList.toggle('active', name === 'terminal');
  $('#btnThemeTw').classList.toggle('active', name === 'twitch');
}
setTheme(localStorage.getItem('corillo_theme') || 'original');
$('#btnThemeOg').addEventListener('click', () => setTheme('original'));
$('#btnThemeTm').addEventListener('click', () => setTheme('terminal'));
$('#btnThemeTw').addEventListener('click', () => setTheme('twitch'));

// ── OVERLAY ──
function showOverlay(title, msg) {
  hideUnmuteBanner();
  $('#ovTitle').textContent = title;
  $('#ovMsg').textContent   = msg;
  $('#overlay').classList.add('show');
  if (_thumbReady) _offlineThumb.classList.add('visible');
}
function hideOverlay() {
  $('#overlay').classList.remove('show');
  _offlineThumb.classList.remove('visible');
}

// ── UNMUTE ──
let _unmuteAttemptPending = false;
function showUnmuteBanner() {
  if (!$('#video').muted) return;
  const isTouch = window.matchMedia('(hover: none) and (pointer: coarse)').matches;
  if (!isTouch && localStorage.getItem('corillo_muted') === 'false') {
    if (_unmuteAttemptPending) return; // ya hay un intento en curso
    // Desktop: intentar auto-desmutear — si Chrome bloquea por autoplay policy
    // (sin gesto del usuario), pausa el video; capturamos ese pause y mostramos banner
    _unmuteAttemptPending = true;
    const v = $('#video');
    const onPause = () => {
      v.removeEventListener('pause', onPause);
      v.muted = true;
      $('#unmuteBtn').classList.add('show');
    };
    v.addEventListener('pause', onPause);
    v.muted = false;
    setTimeout(() => { v.removeEventListener('pause', onPause); _unmuteAttemptPending = false; }, 1000);
  } else {
    // Mobile: siempre requiere tap del usuario — no se puede auto-desmutear
    $('#unmuteBtn').classList.add('show');
  }
}
function hideUnmuteBanner() { $('#unmuteBtn').classList.remove('show'); }
$('#unmuteBtn').addEventListener('click', () => {
  const v = $('#video');
  v.muted = false; v.volume = v.volume || 1;
  if (v.paused) v.play().catch(() => {});
  localStorage.setItem('corillo_muted', 'false');
  hideUnmuteBanner();
});

// ── CONTROLS BAR ──
let ctrlTimer = null;
const ctrlBar = document.getElementById('ctrlBar');
const playerWrap = document.querySelector('.playerWrap');

// ── OFFLINE THUMBNAIL BACKDROP ──
const _offlineThumb = document.createElement('img');
_offlineThumb.className = 'offline-thumb';
let _thumbReady = false;
_offlineThumb.onload = () => {
  _thumbReady = true;
  if ($('#overlay').classList.contains('show')) _offlineThumb.classList.add('visible');
};
_offlineThumb.src = '/assets/thumbs/' + channel + '.jpg';
playerWrap.insertBefore(_offlineThumb, playerWrap.firstChild);

// ── KICK BANNER — avisa al streamer cuando fue kickeado por bitrate alto ──
const _kickBanner = document.createElement('div');
_kickBanner.style.cssText = [
  'display:none','position:absolute','bottom:56px','left:50%','transform:translateX(-50%)',
  'background:rgba(180,30,30,.92)','color:#fff','padding:10px 18px','border-radius:8px',
  'font-size:.82rem','text-align:center','z-index:50','max-width:92%','cursor:pointer',
  'box-shadow:0 2px 12px rgba(0,0,0,.5)','line-height:1.4'
].join(';');
playerWrap.appendChild(_kickBanner);
_kickBanner.addEventListener('click', () => { _kickBanner.style.display = 'none'; });

let _kickBannerTimer = null;
function checkKickBanner() {
  fetch('/assets/kick/' + channel + '.json?t=' + Date.now(), { cache: 'no-store' })
    .then(r => r.ok ? r.json() : null)
    .then(kick => {
      if (!kick || (Date.now() / 1000 - kick.ts) >= 300) return;
      _kickBanner.textContent =
        '⛔ Stream desconectado por bitrate alto (' + kick.kbps.toLocaleString() + ' Kbps). ' +
        'Si eres el streamer y aún no lo corregiste: configura 4,000–4,500 Kbps en OBS / Meld Studio. ' +
        '(Toca para cerrar)';
      _kickBanner.style.display = 'block';
      clearTimeout(_kickBannerTimer);
      _kickBannerTimer = setTimeout(() => { _kickBanner.style.display = 'none'; }, 20000);
    })
    .catch(() => {});
}

function showCtrl() {
  ctrlBar.classList.add('visible');
  clearTimeout(ctrlTimer);
  ctrlTimer = setTimeout(() => ctrlBar.classList.remove('visible'), 3000);
}
playerWrap.addEventListener('mousemove', showCtrl);
playerWrap.addEventListener('mouseleave', () => { clearTimeout(ctrlTimer); ctrlBar.classList.remove('visible'); });
playerWrap.addEventListener('touchstart', showCtrl, { passive: true });

// Play / Pause
const ctrlPlay = document.getElementById('ctrlPlay');
ctrlPlay.addEventListener('click', () => {
  const v = $('#video');
  if (v.paused) v.play().catch(() => {}); else v.pause();
});
$('#video').addEventListener('play',  () => { ctrlPlay.querySelector('i').className = 'fa-solid fa-pause'; });
$('#video').addEventListener('pause', () => { ctrlPlay.querySelector('i').className = 'fa-solid fa-play'; });

// Mute / Volume
const ctrlMute = document.getElementById('ctrlMute');
const ctrlVol  = document.getElementById('ctrlVol');
(function(){ const s = parseFloat(localStorage.getItem('corillo_volume')); if (!isNaN(s)) { $('#video').volume = s; ctrlVol.value = s; } })();
function syncVol() {
  const v = $('#video');
  ctrlVol.value = v.muted ? 0 : v.volume;
  ctrlMute.querySelector('i').className = 'fa-solid ' +
    ((v.muted || v.volume === 0) ? 'fa-volume-xmark' : v.volume < 0.5 ? 'fa-volume-low' : 'fa-volume-high');
}
ctrlMute.addEventListener('click', () => {
  const v = $('#video');
  v.muted = !v.muted;
  if (!v.muted && v.volume === 0) v.volume = 1;
  localStorage.setItem('corillo_muted', v.muted ? 'true' : 'false');
  syncVol();
});
ctrlVol.addEventListener('input', () => {
  const v = $('#video');
  v.volume = +ctrlVol.value;
  v.muted = v.volume === 0;
  localStorage.setItem('corillo_volume', v.volume);
  syncVol();
});
$('#video').addEventListener('volumechange', () => { syncVol(); if (!$('#video').muted) hideUnmuteBanner(); });

// Fullscreen
const ctrlFs = document.getElementById('ctrlFs');
function isFullscreen() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }
function updateFsIcon() { ctrlFs.querySelector('i').className = isFullscreen() ? 'fa-solid fa-compress' : 'fa-solid fa-expand'; }
ctrlFs.addEventListener('click', () => {
  const v = $('#video');
  if (isFullscreen()) {
    (document.exitFullscreen || document.webkitExitFullscreen).call(document).catch(() => {});
  } else if (v.requestFullscreen) {
    v.requestFullscreen().catch(() => {});
  } else if (v.webkitRequestFullscreen) {
    v.webkitRequestFullscreen();
  } else if (v.webkitEnterFullscreen) {
    v.webkitEnterFullscreen();
  }
});
document.addEventListener('fullscreenchange', updateFsIcon);
document.addEventListener('webkitfullscreenchange', updateFsIcon);
$('#video').addEventListener('webkitbeginfullscreen', () => { ctrlFs.querySelector('i').className = 'fa-solid fa-compress'; });
$('#video').addEventListener('webkitendfullscreen',   () => { ctrlFs.querySelector('i').className = 'fa-solid fa-expand'; });

// ── STATS ──
let statsTimer = null;
function startStatsPolling() {
  if (statsTimer) return;
  let hooked = false, emaBitrate = null;
  // Cachear referencias DOM — evita querySelector 5× por segundo (60 veces/min)
  const v        = $('#video');
  const elBitrate = $('#sBitrate');
  const elBuffer  = $('#sBuffer');
  const elLatency = $('#sLatency');
  const elLevel   = $('#sLevel');
  function fmtMbps(bps) {
    if (!bps || !isFinite(bps) || bps <= 0) return '—';
    return (bps / 1_000_000).toFixed(1) + ' Mbps';
  }
  function hookHls() {
    if (hooked) return;
    const h = window._hlsInstance;
    if (!h) return;
    hooked = true;
    h.on(Hls.Events.FRAG_LOADED, (_, data) => {
      try {
        const bytes = data?.stats?.loaded || 0;
        const dur   = data?.frag?.duration || 0;
        if (bytes > 0 && dur > 0) {
          const bps = (bytes * 8) / dur;
          emaBitrate = emaBitrate == null ? bps : emaBitrate * .75 + bps * .25;
        }
      } catch {}
    });
  }
  statsTimer = setInterval(() => {
    if (!v) return;
    hookHls();
    if (v.readyState >= 2 && v.buffered.length) {
      const buf = v.buffered.end(v.buffered.length - 1) - v.currentTime;
      elBuffer.textContent = isFinite(buf) ? buf.toFixed(1) + 's' : '—';
    }
    if (v.seekable?.length > 0) {
      const lat = v.seekable.end(v.seekable.length - 1) - v.currentTime;
      elLatency.textContent = (isFinite(lat) && lat >= 0) ? lat.toFixed(1) + 's' : '—';
    }
    const w = v.videoWidth, h = v.videoHeight;
    elLevel.textContent   = (w > 0 && h > 0) ? `${w}×${h}` : '—';
    elBitrate.textContent = fmtMbps(emaBitrate);
  }, 1000);
}
function stopStatsPolling() {
  clearInterval(statsTimer); statsTimer = null;
  ['sBitrate','sBuffer','sLatency','sLevel'].forEach(id => $('#'+id).textContent = '—');
}

// ── PLAYER ──
let hls = null, retries = 0, retryTimer = null, _nativeErrHandler = null;
window._hlsInstance = null;

function setLive(on) {
  $('#liveDot').className   = 'dot' + (on ? ' on' : '');
  $('#liveTxt').textContent = on ? 'en vivo' : 'offline';
}

function cleanup() {
  if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
  if (_nativeErrHandler) { $('#video').removeEventListener('error', _nativeErrHandler); _nativeErrHandler = null; }
  _unmuteAttemptPending = false;
  stopStatsPolling();
  const v = $('#video');
  try { v.pause(); } catch {}
  v.removeAttribute('src'); v.load();
  if (hls) { try { hls.destroy(); } catch {} hls = null; window._hlsInstance = null; }
  setLive(false);
}

function scheduleRetry(reason) {
  retries++;
  $('#sRetries').textContent = retries;
  $('#retryTxt').textContent = retries;
  // Retries 1-4: agresivo (1200ms c/u) — cubre reconexiones breves del streamer (~5s ventana)
  // Retry 5+: exponencial — canal probablemente offline de verdad
  const wait = retries <= 4
    ? 1200
    : Math.min(30000, 1200 * Math.pow(1.8, Math.min(retries - 4, 9)));
  const secs = Math.round(wait / 1000);
  const offline = reason === 'networkError' || reason === 'Error de HLS nativo';

  // Verificar kick antes de mostrar overlay — evita el flash del mensaje genérico
  fetch('/assets/kick/' + channel + '.json?t=' + Date.now(), { cache: 'no-store' })
    .then(r => r.ok ? r.json() : null)
    .then(kick => {
      if (kick && (Date.now() / 1000 - kick.ts) < 300) {
        showOverlay(
          'Stream pausado temporalmente',
          'El stream fue desconectado por bitrate alto (' + kick.kbps.toLocaleString() + ' Kbps). ' +
          'Si eres el streamer: configura 4,000–4,500 Kbps en OBS o Meld Studio y reconecta. ' +
          'Reintentando en ' + secs + 's…'
        );
      } else {
        showOverlay(
          offline ? 'Sin transmisión' : 'Reconectando',
          (offline ? 'El canal no está en vivo ahora mismo.' : 'Error de conexión.') + ' Reintentando en ' + secs + 's…'
        );
      }
    })
    .catch(() => {
      showOverlay(
        offline ? 'Sin transmisión' : 'Reconectando',
        (offline ? 'El canal no está en vivo ahora mismo.' : 'Error de conexión.') + ' Reintentando en ' + secs + 's…'
      );
    });

  retryTimer = setTimeout(start, wait);
}

function getUrl() {
  const path = mode === 'vertical' ? channel + '-vertical' : channel;
  return '/live/' + encodeURIComponent(path) + '/index.m3u8';
}

async function start() {
  cleanup();
  const url = getUrl();
  $('#hlsTxt').textContent = mode === 'vertical' ? '9:16' : '16:9';
  showOverlay('Cargando', 'Iniciando stream…');
  const v = $('#video');
  v.muted = true; // siempre muted — garantiza autoplay en todos los browsers/dispositivos
                  // showUnmuteBanner() desmutea inmediatamente si el usuario ya lo activó

  if (v.canPlayType('application/vnd.apple.mpegurl')) {
    v.src = url;
    _nativeErrHandler = () => { _nativeErrHandler = null; scheduleRetry('Error de HLS nativo'); };
    v.addEventListener('error', _nativeErrHandler, { once:true });
    try {
      await v.play();
      hideOverlay(); setLive(true); startStatsPolling(); showUnmuteBanner();
    } catch (e) {
      if (e?.name === 'NotAllowedError') {
        showOverlay('Toca para reproducir', 'Presiona el botón para iniciar el stream.');
      }
    }
    return;
  }

  if (window.Hls && Hls.isSupported()) {
    hls = new Hls({ lowLatencyMode:true, backBufferLength:30, maxBufferLength:8, maxLiveSyncPlaybackRate:1.3 });
    window._hlsInstance = hls;
    hls.on(Hls.Events.MEDIA_ATTACHED, () => hls.loadSource(url));
    hls.on(Hls.Events.MANIFEST_PARSED, async () => {
      try {
        await v.play();
        hideOverlay(); setLive(true); startStatsPolling(); showUnmuteBanner();
      } catch {
        showOverlay('Toca para reproducir', 'Presiona el botón para iniciar el stream.');
      }
    });
    hls.on(Hls.Events.ERROR, (_, d) => {
      if (d?.fatal) { cleanup(); scheduleRetry(d.type || 'Error fatal'); }
    });
    hls.attachMedia(v);
    return;
  }

  showOverlay('No compatible', 'Este navegador no puede reproducir HLS. Usa Safari en iOS o un navegador moderno.');
}

$('#ovRetry').addEventListener('click', () => { retries = 0; start(); });
$('#video').addEventListener('waiting',  () => setLive(false));
$('#video').addEventListener('playing',  () => { setLive(true); hideOverlay(); startStatsPolling(); showUnmuteBanner(); checkKickBanner(); });

// ── WAKE LOCK — evita que el móvil apague la pantalla durante el stream ──
let wakeLock = null;
async function requestWakeLock() {
  if (!('wakeLock' in navigator)) return;
  try {
    wakeLock = await navigator.wakeLock.request('screen');
    wakeLock.addEventListener('release', () => { wakeLock = null; });
  } catch {}
}
function releaseWakeLock() {
  if (wakeLock) { wakeLock.release(); wakeLock = null; }
}
$('#video').addEventListener('playing', requestWakeLock);
$('#video').addEventListener('pause',   releaseWakeLock);
$('#video').addEventListener('ended',   releaseWakeLock);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { releaseWakeLock(); }
  else if (!$('#video').paused) { requestWakeLock(); }
});

// ── DARK/LIGHT THEME ──
(function(){
  const root = document.documentElement;
  const btn  = document.getElementById('themeBtn');
  const saved = localStorage.getItem('corillo-theme') || 'dark';
  root.setAttribute('data-theme', saved);
  if (btn) btn.addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('corillo-theme', next);
  });
})();

// ── GRAIN TOGGLE ──
(function(){
  const grainOff = localStorage.getItem('corillo_grain') === 'off';
  if (grainOff) document.body.classList.add('no-grain');
  const btn = document.createElement('button');
  btn.className = 'theme-btn';
  btn.title = grainOff ? 'Activar efecto de grano' : 'Desactivar efecto de grano';
  btn.innerHTML = '&#9641;'; // ▩ — grain/texture icon
  btn.style.fontSize = '.65rem';
  if (grainOff) btn.style.opacity = '.35';
  const themeBtn = document.getElementById('themeBtn');
  themeBtn.parentNode.insertBefore(btn, themeBtn.nextSibling);
  btn.addEventListener('click', () => {
    const nowOff = document.body.classList.toggle('no-grain');
    localStorage.setItem('corillo_grain', nowOff ? 'off' : 'on');
    btn.style.opacity = nowOff ? '.35' : '';
    btn.title = nowOff ? 'Activar efecto de grano' : 'Desactivar efecto de grano';
  });
})();

start();
