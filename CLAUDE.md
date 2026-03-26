# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CORILLO is a static HTML streaming platform for Puerto Rico, built without a build system or framework. Every page is a self-contained `.html` file with inline CSS and vanilla JavaScript. There are no npm packages, no transpilation, and no server-side rendering.

## Architecture

The site is served as static files. **Nginx** handles reverse proxy and SSL, proxying:
- `/mediamtx-api/` → MediaMTX HTTP API (stream state/metadata)
- `/live/{key}/index.m3u8` → MediaMTX HLS output per streamer

**MediaMTX** handles RTMP ingestion and HLS output. Deployed on a **mini server running Ubuntu Server 24.04 LTS** to `/var/www/stream/`.

### Page structure

| Path | Description |
|------|-------------|
| `index.html` | Homepage — channel grid, featured player, live count |
| `player/index.html` | Universal channel player — serves ALL channels via Nginx fallback |
| `multiplayer/index.html` | Multi-stream grid view — shows all live streamers simultaneously |
| `dual/index.html` | Fixed 2-up layout for KATATONIA + MIRA_SANGANOOO (named "KATANA") |
| `join/index.html` | Onboarding/info page for new streamers |
| `configuracion/index.html` | Step-by-step guide for configuring OBS Studio and Meld Studio |

> **Player unification (2026-03-25):** Individual `{canal}/index.html` files were eliminated. Nginx captures the channel key via `location ~ ^/([a-z][a-z0-9_]*)(/|$)` and injects it into `player/index.html` using `sub_filter '__CHANNEL__'`. New streamers work automatically — no HTML file creation needed.

### `player/index.html` — contrato con `player.js` y `player.css`

**CRÍTICO:** `player/index.html` es el único template para todos los canales. `player.js` busca IDs específicos en el DOM — si se cambia el HTML hay que verificar que estos elementos existen:

| ID / Clase | Función |
|------------|---------|
| `#video` | Elemento `<video>` — HLS y VOD offline se cargan aquí |
| `#overlay`, `#ovTitle`, `#ovMsg`, `#ovRetry` | Overlay de estado (cargando / offline / error) |
| `#liveDot`, `#liveTxt` | Indicador en vivo en el nav |
| `#navChAva`, `#navChName`, `#navLivePill` | Canal en la barra de navegación |
| `#chAva`, `#chName`, `#chSub`, `#chBio`, `#chLinks`, `#chHostTag` | Info bar del canal (perfil público) |
| `#statsRow`, `#sBitrate`, `#sBuffer`, `#sLatency`, `#sLevel`, `#sRetries` | Stats en tiempo real |
| `#otherLiveSection`, `#otherLiveList` | Sección "Otros en vivo" |
| `#channelVods`, `#cvodsList`, `#cvodsAll` | Slider de últimas transmisiones |
| `#ctrlBar`, `#ctrlPlay`, `#ctrlMute`, `#ctrlVol`, `#ctrlFs`, `#hlsTxt`, `#retryTxt` | Controles del player |
| `#unmuteBtn` | Banner de unmute (autoplay muted) |
| `#chatCol`, `#chatMsgs`, `#chatInput`, `#chatSend`, `#chatYou`, `#chatChannelLabel` | Chat |
| `#chatToggleBtn`, `#chatCloseBtn`, `#chatRailBtn`, `#railBadge`, `#railIcon` | Toggle de chat |
| `#dropBtn`, `#dropPanel`, `#dropBackdrop` | Menú dropdown / bottom sheet |
| `#btnH`, `#btnV` | Modo 16:9 / 9:16 |
| `#btnThemeOg`, `#btnThemeTm`, `#btnThemeTw` | Temas del player |
| `#themeBtn` | Toggle dark/light del sitio |
| `#twitchLink` | Enlace a Twitch del canal |
| `#chTag` | Compat oculto — no remover |
| `.playerWrap.video-wrap` | Wrapper del video — `player.js` inserta aquí la `offline-thumb` |
| `.app`, `.player-side`, `.chat-side` | Layout principal — clases que usa `player.css` |

**VOD offline playback:** Cuando el canal está offline, `player.js` (líneas ~366–395) busca el último VOD en PocketBase y lo carga en `#video` automáticamente. Requiere que `.playerWrap` tenga la clase `video-wrap`.

**VOD cards:** El script inline en `player/index.html` renderiza las últimas 5 transmisiones. Los links van a `/vods/v/?id={id}` (player de VOD), NO al archivo MP4 directo.

**SEO / meta tags:** El `<head>` contiene `__CHANNEL__` como placeholder. Nginx lo reemplaza con el key del canal via `sub_filter`. No hardcodear valores de canal en el `<head>`.

### Streamers

| Key | Name | Role | Twitch |
|-----|------|------|--------|
| `katatonia` | KATATONIA | host | `katat0nia` (zero, not letter o) |
| `tea` | TEA | — | — |
| `mira_sanganooo` | MIRA_SANGANOOO | — | — |
| `404` | 404 | — | — |
| `elbala` | ELBALA | — | — |
| `marcos` | MARCOS | — | — |

The `STREAMERS` roster lives in **`assets/streamers.js`** (`window.STREAMERS`). Loaded by `index.html`, `multiplayer/index.html`, and `player/index.html`. **Edit only `assets/streamers.js`** when adding or removing a streamer. Each entry: `key` (URL path + MediaMTX path prefix `live/{key}`), `name`, `sub`, `ava`, `color`, `host`, optionally `soon:true` for placeholder cards.

### HLS playback pattern

All pages use `hls.js@1.5.18` from CDN. The same pattern appears everywhere:
1. Check `video.canPlayType('application/vnd.apple.mpegurl')` for native HLS (Safari/iOS)
2. Fall back to `new Hls({ lowLatencyMode:true, ... })` for other browsers
3. Stream URL format: `/live/{encodeURIComponent(key)}/index.m3u8`

Never modify this pattern — it is critical for cross-browser HLS support.

### API polling

The homepage and multiplayer page poll `/mediamtx-api/v3/paths/list` every 15 seconds (`POLL_MS = 15000`) with an 8-second client-side cache (`CACHE_S`/`CACHE_MS`). The fetch has a `API_TIMEOUT_MS = 5000` abort timeout. A `ready: true` field on a path item means the stream is live. Viewer count comes from `path.readers.length`.

Both the homepage and multiplayer page pause polling via `visibilitychange` when the tab is hidden and resume (with an immediate fetch, `cache.t = 0`) when it becomes visible again.

### Shared assets

| File | Contains |
|------|----------|
| `assets/styles.css` | Design tokens (`:root` vars), light-mode overrides, CSS reset, grain overlay (`body::after`), `@keyframes blink`, `.theme-btn` |
| `assets/streamers.js` | `window.STREAMERS` roster — single source of truth |
| `assets/og-image.html` | Source template for the OG social preview image (1200×630 SVG). To regenerate `og-image.png`: open in a headless browser and screenshot at exactly 1200×630. |

All 11 HTML pages link `styles.css`. Each page's inline `<style>` keeps only page-specific layout and component rules.

### Styling rules

- **All global styles go in `assets/styles.css`** — never hardcode colors in HTML files.
- **Always use CSS variables** for colors, never raw hex values.
- Dark mode is default. Light mode uses `data-theme="light"` on `<html>`, saved in `localStorage` as `'corillo-theme'`.
- Font Awesome is loaded from `cdnjs.cloudflare.com` (free tier, no account/kit needed).
- Fonts: Bebas Neue (display), Space Mono (mono/UI), DM Sans (body) — loaded from Google Fonts.

## Server Infrastructure

**Host:** Mini server, Ubuntu Server 24.04.4 LTS (`corillo-server`) — kernel 6.8.0-106-generic x86_64
**CPU:** Intel Core Ultra 9 285H — 16 cores (no HT), ~48°C idle
**User:** `corillo-adm`
**IP local:** `192.168.8.166`
**SSH:** puerto 22
**Web root:** `/var/www/stream/` (this repo deploys here)
**Disk:** ~98GB total (~40% usado, as of 2026-03-24)
**RAM:** ~3% uso típico en idle

### Versiones de software

| Software | Versión |
|----------|---------|
| Ubuntu | 24.04.4 LTS |
| Nginx | 1.24.0 |
| MediaMTX | v1.17.0 |
| PocketBase | 0.36.7 |
| Python (venv VOD) | 3.12.3 |
| httpx | 0.28.1 |

### systemd Services

| Service | Description |
|---------|-------------|
| `mediamtx.service` | MediaMTX — RTMP ingestion + HLS output |
| `nginx.service` | Nginx reverse proxy + SSL |
| `pocketbase.service` | PocketBase — auth, streamer profiles, VODs |
| `corillo-api.service` | Corillo API — public profiles + stream key management |
| `corillo-auth.service` | RTMP stream key validation |
| `corillo-bot.service` | Chat API bot |
| `corillo-telegram.service` | Telegram webhook — streamer approval + live notifications |
| `corillo-thumbs.service` | Live thumbnail generator — polling `/mediamtx-api/v3/paths/list` cada 60s, captura frame del HLS activo y lo guarda en `/var/www/stream/thumbs/{channel}.jpg` |

### Key paths on the server

| Path | Description |
|------|-------------|
| `/var/www/stream/` | Web root — this repo deployed here |
| `/var/vods/` | VOD recordings stored here (NOT in the web root) — format: `/var/vods/live/{channel}/{timestamp}.mp4` |
| `/home/corillo-adm/corillo-vod/` | VOD post-processing script (separate from repo) |
| `/home/corillo-adm/corillo-vod/venv/` | Python virtualenv for VOD script |
| `/home/corillo-adm/corillo-bot/` | Chat bot + `.env` file with shared secrets |
| `/home/corillo-adm/corillo-bot/.env` | Env file loaded by `vod-process.py` (PB_URL, PB_ADMIN_EMAIL, PB_ADMIN_PASS) |
| `/var/log/corillo-vod.log` | VOD processing log |
| `/var/log/corillo-thumbs.log` | Live thumbnail generator log |
| `/etc/mediamtx/mediamtx.yml` | MediaMTX config |

### VOD pipeline

MediaMTX records streams to `/var/vods/live/{channel}/{timestamp}.mp4` with segments up to 6 hours.

On `runOnRecordSegmentComplete`, MediaMTX calls:
```
/home/corillo-adm/corillo-vod/venv/bin/python /home/corillo-adm/corillo-vod/vod-process.py
```

**IMPORTANT:** The live VOD script is at `/home/corillo-adm/corillo-vod/vod-process.py` — this is **separate from** `scripts/vod-process.py` in the repo. Changes to `scripts/vod-process.py` must be manually synced to the server path.

The script:
1. Reads `MTX_PATH` and `MTX_SEGMENT_PATH` env vars from MediaMTX
2. Looks up the channel in PocketBase (`streamers` collection) — checks `vod_enabled` and `vod_plan`
3. Remuxea el fmp4 a MP4 progresivo con `faststart` (moov al inicio) para que sea streamable
4. Generates a thumbnail JPEG via ffmpeg (`{timestamp}.jpg`)
5. Generates a 4s muted MP4 preview clip via ffmpeg (`{timestamp}-preview.mp4`)
6. Saves VOD record to PocketBase (`vods` collection) with `thumb` and `preview` URLs
7. Applies retention policy (`free` plan: keep 5, `pro` plan: unlimited)

Thumbnail/preview URLs are served as `/vods/{channel}/{filename}` — Nginx must map this to `/var/vods/live/{channel}/`.

### MediaMTX recording config (relevant excerpt)

```yaml
recordPath: /var/vods/%path/%Y-%m-%d_%H-%M-%S
recordFormat: fmp4
recordSegmentDuration: 6h
paths:
  "~^live/":
    record: yes
    runOnRecordSegmentComplete: /home/corillo-adm/corillo-vod/venv/bin/python /home/corillo-adm/corillo-vod/vod-process.py
```

## Deployment

Push to `main` → GitHub Actions deploys automatically via SSH on port 2222 to `corillo.live`.

```bash
git push origin main  # triggers deploy
```

## Development

No build step — open files directly in a browser or serve locally:

```bash
python -m http.server 8080
# or
npx serve .
```

For live status and HLS playback, a MediaMTX instance must be running with the Nginx proxy configured.

### LocalStorage keys

Keep these keys stable — they're spread across every replicated page and changing one requires a coordinated update with migration logic:

| Key | Scope | Values |
|-----|-------|--------|
| `corillo-theme` | All pages | `'dark'` / `'light'` |
| `corillo_theme` | All player pages (via `player/index.html`) | `'original'` / `'terminal'` / `'twitch'` (player visual theme, shared across all players) |
| `corillo_chat` | `player/index.html` | `'visible'` / `'hidden'` (chat panel visibility) |

## Notas operacionales

### Sincronizar vod-process.py al servidor

El script vivo en `/home/corillo-adm/corillo-vod/vod-process.py` es **independiente del repo**. Cada vez que se haga deploy y se modifique `scripts/vod-process.py`, hay que copiarlo manualmente:

```bash
sudo cp /var/www/stream/scripts/vod-process.py /home/corillo-adm/corillo-vod/vod-process.py
```

### Permisos en /var/vods/

MediaMTX graba como `root`, pero `vod-process.py` corre como `corillo-adm`. Para que el script pueda escribir thumbnails y previews junto a los MP4:

```bash
sudo chown -R corillo-adm:corillo-adm /var/vods/
```

Esto hay que repetirlo si MediaMTX crea nuevas carpetas de canal (corriendo como root).

### Procesar VODs manualmente

Si un VOD quedó sin procesar (ej. porque el script falló o el canal tenía `vod_enabled=false`), se puede reprocesar manualmente:

```bash
MTX_PATH=live/{channel} MTX_SEGMENT_PATH=/var/vods/live/{channel}/{timestamp}.mp4 \
  /home/corillo-adm/corillo-vod/venv/bin/python /home/corillo-adm/corillo-vod/vod-process.py
```

Nota: la retención aplica en cada ejecución — con plan `free`, solo se conservan los 5 más recientes.

### corillo-thumbs: permisos del log

El servicio `corillo-thumbs` escribe en `/var/log/corillo-thumbs.log`. Si el archivo no existe o es de `root`, el servicio falla al arrancar. Fix:

```bash
sudo touch /var/log/corillo-thumbs.log
sudo chown corillo-adm:corillo-adm /var/log/corillo-thumbs.log
sudo systemctl restart corillo-thumbs
```

### Variables de entorno de MediaMTX (v1.17+)

MediaMTX provee estas variables al llamar `runOnRecordSegmentComplete`:

| Variable | Valor |
|----------|-------|
| `MTX_PATH` | Path del stream, ej. `live/katatonia` |
| `MTX_SEGMENT_PATH` | Ruta absoluta del archivo grabado |
| `MTX_SEGMENT_DURATION` | Duración del segmento en segundos |

**Importante:** En versiones anteriores era `MTX_RECORD_PATH` — la versión correcta para v1.17+ es `MTX_SEGMENT_PATH`.

### VOD player — autoplay y sonido

El player de VODs (`vods/v/index.html`) usa `autoplay muted` para cumplir con la política de autoplay de los navegadores. Aparece un botón "Activar sonido" encima del video que desactiva el mute al presionarlo.

## Inventario completo de páginas

| Ruta | Descripción |
|------|-------------|
| `index.html` | Homepage — featured player con rotación, grid de canales, sidebar/drawer |
| `player/index.html` | Player universal — sirve todos los canales vía fallback Nginx (`try_files`) |
| `multiplayer/index.html` | Grid multi-stream — todos los streamers en vivo simultáneamente |
| `dual/index.html` | Layout fijo 2-up KATATONIA + MIRA_SANGANOOO ("KATANA") |
| `vods/index.html` | Browser de VODs — filtros por canal, cards con preview en hover |
| `vods/v/index.html` | Player individual de VOD — autoplay muted, botón "Activar sonido" |
| `join/index.html` | Formulario de onboarding para nuevos streamers |
| `configuracion/index.html` | Guía paso a paso OBS Studio y Meld Studio |
| `perfil/index.html` | Dashboard del streamer — stream key, editar perfil, VOD settings |
| `perfil/reset/index.html` | Reset de contraseña |
| `streamers/index.html` | Directorio de streamers con status online/offline |
| `legal/index.html` | Términos de servicio |
| `dmca/index.html` | Info DMCA |
| `faq/index.html` | Preguntas frecuentes |
| `roadmap/index.html` | Roadmap de la plataforma |
| `dev/index.html` | Página de debug/desarrollo |
| `natcheck/index.html` | Utilidad de NAT test |
| `antibufferbloat-pro/index.html` | Feature page |
| `streamer-pro/index.html` | Feature page |

## Assets compartidos — detalle técnico

### `assets/streamers.js`

Single source of truth de todos los streamers. Estructura de cada entrada:

```javascript
{
  key: 'katatonia',           // URL path + prefijo MediaMTX (live/{key})
  name: 'KATATONIA',          // Nombre display
  sub: 'Gaming · Aibonito PR', // Subtítulo/descripción
  ava: 'K',                   // Letra del avatar
  color: 'linear-gradient(135deg,#e8c84a,#c09020)', // CSS color/gradient
  host: true,                 // Flag de host (opcional)
  twitch: 'katat0nia',        // Handle Twitch (opcional)
  soon: false                 // Placeholder (opcional)
}
```

14 streamers activos + 1 placeholder (`soon: true`). Auto-actualizado por `telegram/server.py` vía GitHub API al aprobar nuevos streamers.

### `assets/styles.css` — Variables CSS globales

```css
:root {
  /* Fondo */
  --ink:     #030a0e;    /* bg oscuro */
  --surface: #071118;    /* bg secundario */
  --panel:   #0d1c28;    /* panels/dialogs */

  /* Texto */
  --white:   #e8f6ff;    /* texto claro */
  --muted:   #3a6070;    /* texto muted */

  /* Colores de acento */
  --accent:  #00bfff;    /* cyan primario */
  --live:    #00ff9d;    /* verde "en vivo" */

  /* Bordes */
  --border:   rgba(0,191,255,.08);   /* sutil */
  --border-h: rgba(0,191,255,.2);    /* hover */

  /* Tipografía */
  --mono:    'Space Mono', monospace;
  --display: 'Bebas Neue', cursive;
  --body:    'DM Sans', sans-serif;

  /* Escala de texto */
  --text-2xs: .7rem;
  --text-xs:  .75rem;
  --text-sm:  .85rem;
  --text-base: 1rem;
  --text-lg:  1.1rem;
}
```

Light mode: `[data-theme="light"]` — cambia `--ink` a `#eef7fb`, `--white` a `#051015`, `--accent` a `#0088bb`.

Grain overlay: `body::after` con SVG fractalNoise — desactivado en pantallas HDR (`@media (dynamic-range: high)`), toggle con clase `.no-grain`.

### `assets/player.js` — Player compartido (~900 líneas)

Cargado por todas las páginas individuales de canal. Expone lógica completa del player.

**Constantes clave:**
```javascript
RECONNECT_DELAYS = { FAST: 1200, BASE: 1200, MAX: 30000, BACKOFF_FACTOR: 1.8 }
MAX_RETRIES_BEFORE_OFFLINE = 4   // Antes de entrar en watch mode
KICK_BANNER_DURATION = 20000     // ms que dura el banner de kick
KICK_MAX_AGE = 300               // segundos máx de antigüedad del kick
STATS_INTERVAL = 1000            // ms entre actualizaciones de stats
WATCH_INTERVAL = 15000           // ms entre checks de stream en watch mode
STALL_CHECK_INTERVAL = 5000      // ms entre checks de stall (HLS nativo)
```

**Estado global `App`:**
```javascript
App = {
  channel, mode, hls, rtcPc, retries, retryTimer,
  watchTimer, statsTimer, kickBannerTimer, ctrlTimer,
  wakeLock, sessionAc,       // AbortController por sesión
  useWebRTC, unmuteAttemptPending,
  emaBitrate,                // EMA del bitrate (75/25)
  volume, muted
}
```

**Funciones principales:**

| Función | Descripción |
|---------|-------------|
| `startPlayer()` | Entry point — decide HLS nativo vs hls.js vs WebRTC |
| `setupNativeHLS(url)` | HLS nativo para Safari/iOS, incluye stall detection |
| `setupHlsJs(url)` | Fallback con hls.js, config: lowLatency off, buffer 8-12s, max 1.1x playback rate |
| `startWebRTC()` | WHEP protocol — `POST /webrtc/live/{channel}_rtc/whep` |
| `scheduleRetry(reason)` | Backoff exponencial: 1.2s→1.8s→2.7s→...→30s |
| `startWatch()` | Poll `/mediamtx-api/v3/paths/list` cada 15s esperando que el stream vuelva |
| `startStatsPolling()` | EMA bitrate por `FRAG_LOADED`, buffer/latency/calidad cada 1s |
| `cleanup()` | Destruye HLS/RTC, aborta sessionAc, detiene video |
| `setMode('horizontal'/'vertical')` | Cambia aspect ratio, guarda en URL (`?mode=vertical`) |
| `setTheme('original'/'terminal'/'twitch')` | Cambia tema visual, guarda en localStorage |
| `requestWakeLock()` / `releaseWakeLock()` | Screen Wake Lock API |
| `loadProfile()` | `GET /chat-api/profile/{channel}` — avatar, bio, links, panels |
| `loadOthersLive()` | Muestra otros streamers en vivo en el sidebar |
| `checkKickBanner()` | Revisa `/assets/kick/{channel}.json` — muestra banner si fue kickeado |
| `initChannelUI()` | Pinta avatar, nombre, sub, host tag desde `STREAMERS` |

**EMA Bitrate:**
```javascript
// Hook en FRAG_LOADED de hls.js
bps = (bytes_loaded * 8) / fragment_duration
emaBitrate = emaBitrate * 0.75 + bps * 0.25  // peso 75/25
```

**Retry con backoff:**
```javascript
// retries 1-4: FAST = 1200ms
// retries 5+: min(30000, 1200 * 1.8^(retries-4))
// → 2.2s, 3.9s, 7s, 12.6s, 22.7s, 30s (max)
```

### `assets/chat.js` — Chat WebSocket (~126 líneas)

```javascript
// Conexión
WS_URL = `wss://{host}/chat-api/ws/{channel}?user={username}`

// Reconexión con backoff
delay = Math.min(30000, 3000 * Math.pow(1.5, retries))
// → 3s, 4.5s, 6.75s, ... → 30s max

// Colores de usuario (determinístico por nombre, 10 colores)
function userColor(name) {
  // Hash del nombre → índice en palette de 10 colores
  // Misma persona siempre tiene el mismo color
}

// Tipos de mensajes entrantes
{ type: 'welcome', user: 'NombreAsignado' }
{ type: 'message', user, text, ts, bot: false }
{ type: 'system', text }

// Límite: 280 caracteres por mensaje
// Rate limit server-side: 1 mensaje/segundo
```

**LocalStorage keys adicionales de chat:**
```
corillo_username  — nombre de usuario guardado
corillo_volume    — nivel de volumen (0.0 – 1.0)
corillo_muted     — estado muted ('true'/'false')
corillo_grain     — grain overlay ('on'/'off')
```

### `assets/player.css`

Estilos del player: layout 2 columnas (player + chat 300px), overlay, control bar con auto-hide (3s), canal info bar, stats row, dropdown menu, responsive (<820px chat pasa a bottom sheet).

## Backend services — detalle técnico

### `api/server.py` — API pública (puerto 3004)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/profile/{key}` | GET | Perfil público del streamer desde PocketBase |
| `/regen-stream-key` | POST | Regenera stream key (requiere token de usuario) |
| `/health` | GET | Health check |

- Token admin cacheado 24h
- CORS: `corillo.live`, `localhost:8080`
- Avatar URL: `{PB_URL}/api/files/streamers/{id}/{avatar}`

### `auth/server.py` — Validación RTMP (puerto 3002)

Webhook de autenticación de MediaMTX. Valida stream keys contra PocketBase.

```
actions permitidas automáticamente:
  read, playback → 200 (viewers)
  api, metrics, pprof desde 127.0.0.1 → 200

publish:
  extrae channel y secret del path
  valida contra PocketBase (cache 60s por canal)
  → 200 si válido, 401 si no
```

### `chat/server.py` — Chat + Bot (puerto 3001)

| Endpoint | Descripción |
|----------|-------------|
| `WebSocket /ws/{channel}` | Chat en vivo — historial desde SQLite (últimos 50 msgs) |
| `POST /message` | REST API para consultas al bot (Claude haiku) |
| `GET /digest` | Resumen de 1 oración del estado de streams (cacheado 120s) |
| `GET /health` | Health check |

**Bot:**
- Modelo: `claude-haiku-4-5-20251001`
- Se activa con `@bot {pregunta}` en el chat
- Recibe estado actual de streams en el system prompt
- Max 512 tokens por respuesta

**Room:**
- Cache de live: 12s TTL
- Rate limit: 1 mensaje/segundo por usuario
- Historia: últimos 50 mensajes en SQLite + en memoria
- Nombres: aleatorios de lista boricua + sufijo 2 dígitos

### `telegram/server.py` — Webhook + Aprobación (puerto 3003)

| Endpoint | Descripción |
|----------|-------------|
| `POST /join` | Procesa solicitud de nuevo streamer |
| `POST /telegram/webhook` | Recibe updates del bot de Telegram |

**Flujo de onboarding:**
1. `POST /join` desde `join/index.html`
2. Validación: 3-24 chars, alfanumérico + underscore, no reservados, honeypot
3. Rate limit: 3 solicitudes/hora por IP
4. Telegram: notificación con botones ✅ Aprobar / ❌ Rechazar
5. Admin aprueba → `auto_create_streamer()`:
   - Actualiza `assets/streamers.js` via GitHub API
   - Crea registro en PocketBase (email, password generado, stream_key)
   - Notifica al streamer
   - ~~Crea `{handle}/index.html`~~ — eliminado: Nginx sirve `player/index.html` automáticamente para cualquier canal no encontrado

## Scripts — detalle técnico

### `scripts/vod-process.py`

Ver sección "VOD pipeline" arriba. Funciones internas:

| Función | Descripción |
|---------|-------------|
| `pb_token()` | Obtiene token admin de PocketBase |
| `get_streamer(channel, token)` | Busca streamer en colección `streamers` |
| `remux_faststart(filepath)` | fmp4 → MP4 con moov al inicio (ffmpeg `-movflags +faststart`) |
| `generate_thumbnail(filepath, duration)` | JPEG 640px, quality 3, seek al `min(10, 20% duración)` |
| `generate_preview(filepath, duration)` | Clip MP4 4s, libx264 baseline, CRF 32, sin audio |
| `save_vod(...)` | POST a colección `vods` de PocketBase |
| `apply_retention(channel, keep, token)` | Borra VODs más viejos si excede el plan |
| `get_duration(filepath)` | ffprobe para obtener duración en segundos |

### `scripts/thumb-gen.py`

Daemon que genera thumbnails de streams en vivo cada 60s.

```python
MEDIAMTX_API = "http://127.0.0.1:9997"
HLS_BASE     = "http://127.0.0.1:8888"
THUMB_DIR    = Path("/var/www/stream/assets/thumbs")
INTERVAL     = 60  # segundos

# Por cada stream con ready=true:
# ffmpeg -i /live/{key}/index.m3u8 -vframes 1 → {key}.jpg
# ffmpeg -i /live/{key}/index.m3u8 -t 4 → {key}-preview.mp4
```

### `scripts/bitrate-monitor.py`

Daemon de monitoreo de bitrate con auto-kick.

**Thresholds:**

| Nivel | Kbps | Acción |
|-------|------|--------|
| Warn | 5,000 | Telegram: ⚠️ |
| Alert | 8,000 | Telegram: 🔴 |
| Auto-kick | 6,500 | 2 polls consecutivos → corta conexión TCP |

**Exentos de kick (solo alertas):** `streamerpro`, `katatonia`, `marcos`

**Mecanismo de kick:**
1. Poll 1 ≥ 6,500 Kbps → strike 1, warning Telegram
2. Poll 2 ≥ 6,500 Kbps → strike 2 → `sudo ss -K dst {ip} dport {port}` (corta TCP)
3. Escribe `/assets/kick/{channel}.json` → el player muestra banner
4. Cooldown: 35s antes de poder volver a kickear
5. Recuperación: si baja, limpia strikes y notifica ✅

### `scripts/pb-setup-vods.py`

Script one-time para crear la colección `vods` en PocketBase y agregar campos `vod_enabled`/`vod_plan` a `streamers`. No se ejecuta en producción, solo en setup inicial.

## PocketBase — colecciones

### `streamers`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `key` | text | Handle del canal (URL path) |
| `display_name` | text | Nombre display |
| `bio` | text | Descripción del canal |
| `color` | text | Color CSS |
| `twitch` | text | Handle de Twitch |
| `instagram` | text | Handle de Instagram |
| `tiktok` | text | Handle de TikTok |
| `avatar` | file | Foto de perfil |
| `panels` | json | Panels personalizados |
| `stream_key` | text | Clave de stream (secreta) |
| `stream_key_full` | text | `{handle}?secret={stream_key}` |
| `vod_enabled` | bool | Habilita grabación de VODs |
| `vod_plan` | select | `free` (keep 5) / `pro` (ilimitado) |
| `active` | bool | Canal activo |
| `verified` | bool | Canal verificado |

### `vods`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `channel` | text | Key del canal |
| `filename` | text | Nombre del archivo MP4 |
| `filepath` | text | Ruta absoluta en el servidor |
| `duration` | number | Duración en segundos |
| `size` | number | Tamaño en bytes |
| `date` | date | Fecha de grabación |
| `thumb` | text | URL del thumbnail (`/vods/{channel}/{ts}.jpg`) |
| `preview` | text | URL del preview clip (`/vods/{channel}/{ts}-preview.mp4`) |

**Permisos:** listRule/viewRule = `""` (público). deleteRule = `'channel = @request.auth.key'` (streamer puede borrar sus propios VODs).

## Flujo completo de streaming

```
1. Streamer → RTMP
   rtmp://corillo.live/live/{key}?secret={stream_key}
            ↓
2. MediaMTX auth hook → auth/server.py:3002
   Valida stream_key vs PocketBase (cache 60s)
            ↓
3. MediaMTX acepta → HLS disponible
   /live/{key}/index.m3u8
   Grabación: /var/vods/live/{key}/{timestamp}.mp4
            ↓
4. Browser solicita HLS
   Safari: nativo | Chrome/Firefox: hls.js
   Alternativa: WebRTC WHEP (/webrtc/live/{key}_rtc/whep)
            ↓
5. thumb-gen.py (daemon, cada 60s)
   Captura frame → /assets/thumbs/{key}.jpg
   Captura clip 4s → /assets/thumbs/{key}-preview.mp4
            ↓
6. bitrate-monitor.py (daemon, cada 30s)
   Calcula Kbps desde bytesReceived delta
   Si ≥ 6,500 Kbps × 2 polls → kick TCP + notify Telegram
            ↓
7. Fin del segmento (cada 6h o fin stream)
   MediaMTX → runOnRecordSegmentComplete → vod-process.py
   Remux → thumbnail → preview → PocketBase → retención
```

## Integraciones externas

| Servicio | Uso |
|----------|-----|
| **Anthropic Claude** | Chat bot (haiku), digest de estado de streams |
| **PocketBase** | Auth, perfiles de streamers, colección vods, archivos |
| **GitHub API** | Auto-crear páginas HTML y actualizar streamers.js al aprobar streamers |
| **Telegram Bot** | Alertas de bitrate, notificaciones de /join, aprobación de streamers |
| **hls.js CDN** | Playback HLS en Chrome/Firefox (v1.5.18) |
| **Font Awesome CDN** | Íconos (v6.5.1, free tier) |
| **Google Fonts** | Bebas Neue, DM Sans, Space Mono |

## Conventions

- The grain overlay (`body::after` with SVG fractalNoise) appears on every page — it's intentional, do not remove it.
- Player pages derive the channel key from `location.pathname` — `pathParts[0]` is the first path segment (e.g. `/tea/` → `"tea"`). The `<title>` and Twitch link are updated dynamically by JS on load.
- The `dual/` page is hardcoded to KATATONIA + MIRA_SANGANOOO and is not a generic template.
