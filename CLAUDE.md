# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CORILLO is a static HTML streaming platform for Puerto Rico, built without a build system or framework. Every page is a self-contained `.html` file with inline CSS and vanilla JavaScript. There are no npm packages, no transpilation, and no server-side rendering.

## Architecture

The site is served as static files. **Caddy** handles reverse proxy and SSL, proxying:
- `/mediamtx-api/` → MediaMTX HTTP API (stream state/metadata)
- `/live/{key}/index.m3u8` → MediaMTX HLS output per streamer

**MediaMTX** handles RTMP ingestion and HLS output. Deployed on a **Raspberry Pi 3B+** to `/var/www/stream/`.

### Page structure

| Path | Description |
|------|-------------|
| `index.html` | Homepage — channel grid, featured player, live count |
| `katatonia/index.html` | Individual channel player (the canonical player template) |
| `{streamer}/index.html` | Same player template replicated per streamer (404, elbala, mira_sanganooo, tea) |
| `multiplayer/index.html` | Multi-stream grid view — shows all live streamers simultaneously |
| `dual/index.html` | Fixed 2-up layout for KATATONIA + MIRA_SANGANOOO (named "KATANA") |
| `join/index.html` | Onboarding/info page for new streamers |

### Streamers

| Key | Name | Role | Twitch |
|-----|------|------|--------|
| `katatonia` | KATATONIA | host | `katat0nia` (zero, not letter o) |
| `tea` | TEA | — | — |
| `mira_sanganooo` | MIRA_SANGANOOO | — | — |
| `404` | 404 | — | — |
| `elbala` | ELBALA | — | — |

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

All 9 HTML pages link `styles.css`. Each page's inline `<style>` keeps only page-specific layout and component rules.

### Styling rules

- **All global styles go in `assets/styles.css`** — never hardcode colors in HTML files.
- **Always use CSS variables** for colors, never raw hex values.
- Dark mode is default. Light mode uses `data-theme="light"` on `<html>`, saved in `localStorage` as `'corillo-theme'`.
- Font Awesome is loaded from `cdnjs.cloudflare.com` (free tier, no account/kit needed).
- Fonts: Bebas Neue (display), Space Mono (mono/UI), DM Sans (body) — loaded from Google Fonts.

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

For live status and HLS playback, a MediaMTX instance must be running with the Caddy proxy configured.

### LocalStorage keys

Keep these keys stable — they're spread across every replicated page and changing one requires a coordinated update with migration logic:

| Key | Scope | Values |
|-----|-------|--------|
| `corillo-theme` | All pages | `'dark'` / `'light'` |
| `corillo_theme` | All player pages (katatonia, 404, tea, mira_sanganooo, elbala) | `'original'` / `'terminal'` / `'twitch'` (player visual theme, shared across all players) |
| `corillo_chat` | `katatonia/index.html` | `'visible'` / `'hidden'` (chat panel visibility) |

## Conventions

- The grain overlay (`body::after` with SVG fractalNoise) appears on every page — it's intentional, do not remove it.
- Player pages derive the channel key from `location.pathname` — `pathParts[0]` is the first path segment (e.g. `/tea/` → `"tea"`). The `<title>` and Twitch link are updated dynamically by JS on load.
- The `dual/` page is hardcoded to KATATONIA + MIRA_SANGANOOO and is not a generic template.
