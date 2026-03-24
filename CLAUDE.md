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
| `katatonia/index.html` | Individual channel player (the canonical player template) |
| `{streamer}/index.html` | Same player template replicated per streamer (404, elbala, marcos, mira_sanganooo, tea) |
| `multiplayer/index.html` | Multi-stream grid view — shows all live streamers simultaneously |
| `dual/index.html` | Fixed 2-up layout for KATATONIA + MIRA_SANGANOOO (named "KATANA") |
| `join/index.html` | Onboarding/info page for new streamers |
| `configuracion/index.html` | Step-by-step guide for configuring OBS Studio and Meld Studio |

### Streamers

| Key | Name | Role | Twitch |
|-----|------|------|--------|
| `katatonia` | KATATONIA | host | `katat0nia` (zero, not letter o) |
| `tea` | TEA | — | — |
| `mira_sanganooo` | MIRA_SANGANOOO | — | — |
| `404` | 404 | — | — |
| `elbala` | ELBALA | — | — |
| `marcos` | MARCOS | — | — |

The `STREAMERS` roster lives in **`assets/streamers.js`** (`window.STREAMERS`). Only `index.html` and `multiplayer/index.html` load it — individual player pages don't use it. **Edit only `assets/streamers.js`** when adding or removing a streamer. Each entry: `key` (URL path + MediaMTX path prefix `live/{key}`), `name`, `sub`, `ava`, `color`, `host`, optionally `soon:true` for placeholder cards.

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

**Host:** Mini server, Ubuntu Server 24.04 LTS (`corillo-server`)
**User:** `corillo-adm`
**Web root:** `/var/www/stream/` (this repo deploys here)
**Reverse proxy:** Nginx 1.24
**Disk:** ~98GB total, ~56GB free (as of 2026-03-23)

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
| `corillo_theme` | All player pages (katatonia, 404, tea, mira_sanganooo, elbala, marcos) | `'original'` / `'terminal'` / `'twitch'` (player visual theme, shared across all players) |
| `corillo_chat` | `katatonia/index.html` | `'visible'` / `'hidden'` (chat panel visibility) |

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

## Conventions

- The grain overlay (`body::after` with SVG fractalNoise) appears on every page — it's intentional, do not remove it.
- Player pages derive the channel key from `location.pathname` — `pathParts[0]` is the first path segment (e.g. `/tea/` → `"tea"`). The `<title>` and Twitch link are updated dynamically by JS on load.
- The `dual/` page is hardcoded to KATATONIA + MIRA_SANGANOOO and is not a generic template.
