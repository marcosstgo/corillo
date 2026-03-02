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

The `STREAMERS` array is duplicated across `index.html`, `multiplayer/index.html`, and all individual player pages. **Update every copy** when adding or removing a streamer. Each entry: `key` (URL path + MediaMTX path prefix `live/{key}`), `name`, `sub`, `ava`, `color`, `host`, optionally `soon`.

### HLS playback pattern

All pages use `hls.js@1.5.18` from CDN. The same pattern appears everywhere:
1. Check `video.canPlayType('application/vnd.apple.mpegurl')` for native HLS (Safari/iOS)
2. Fall back to `new Hls({ lowLatencyMode:true, ... })` for other browsers
3. Stream URL format: `/live/{encodeURIComponent(key)}/index.m3u8`

Never modify this pattern — it is critical for cross-browser HLS support.

### API polling

The homepage and multiplayer page poll `/mediamtx-api/v3/paths/list` every 15 seconds (`POLL_MS = 15000`) with an 8-second client-side cache. A `ready: true` field on a path item means the stream is live. Viewer count comes from `path.readers.length`.

### Styling rules

- **All global styles go in `assets/styles.css`** — never hardcode colors in HTML files.
- **Always use CSS variables** from `styles.css` for colors, never raw hex values.
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
| `corillo_theme` | `katatonia/index.html` | `'original'` / `'terminal'` / `'twitch'` (player visual theme) |
| `kata_theme` | Player pages (404, tea, mira_sanganooo, elbala) | `'original'` / `'terminal'` / `'twitch'` |
| `corillo_chat` | `katatonia/index.html` | `'1'` / `'0'` (chat panel visibility) |

## Conventions

- The grain overlay (`body::after` with SVG fractalNoise) appears on every page — it's intentional, do not remove it.
- Player pages derive the channel key from their directory name (hardcoded in the HTML, not read from the URL).
- The `dual/` page is hardcoded to KATATONIA + MIRA_SANGANOOO and is not a generic template.
