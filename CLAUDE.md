# CLAUDE.md — Corillo Technical Reference

Documentación técnica completa de corillo.live. Actualizada 2026-05-19.

---

## Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Frontend | Astro (SSG) | 6.3.5 |
| CSS framework | Corillo CSS (propio) | v1.4 |
| Runtime | Node.js | 22 |
| Backend services | Python / FastAPI / Uvicorn | 3.12 / 0.135 |
| Base de datos | PocketBase | 0.36.7 |
| Streaming | MediaMTX | — |
| Web server | nginx | — |
| OS | Ubuntu Server 24.04 LTS | — |

---

## Repositorio

**GitHub:** `marcosstgo/corillo` (público)
**Working tree en producción:** `/var/www/stream/`
**CI/CD:** GitHub Actions → `.github/workflows/deploy.yml`

El repo es el monorepo completo. `/var/www/stream/` es el clone directo donde se edita, se hace build y se pushea. No hay entorno separado de staging.

### Deploy pipeline

Cada push a `main` ejecuta en orden:
1. Bump de versión en `version.json`
2. `npm ci` + `npm run build` (Astro → `dist/`)
3. `rsync` del repo completo a `/var/www/stream/` en el servidor
4. Si `nginx.conf` cambió → `sudo cp` a `/etc/nginx/nginx.conf` + `nginx reload`
5. Si `mediamtx.yml` cambió → reinicia MediaMTX
6. Despliega `api/server.py` → `/home/corillo-adm/corillo-api/` + reinicia servicio
7. Despliega `auth/server.py` → `/home/corillo-adm/corillo-auth/` + reinicia servicio
8. Despliega `chat/server.py` → `/home/corillo-adm/corillo-bot/` + reinicia servicio
9. Despliega `telegram/server.py` → `/home/corillo-adm/corillo-telegram/` + reinicia servicio
10. Despliega scripts VOD y bitrate-monitor

> **IMPORTANTE:** El nginx que importa es `/var/www/stream/nginx.conf` en el repo.
> Editar `/etc/nginx/nginx.conf` directamente es temporal — el CI lo sobreescribe en el próximo push.

---

## Servicios en producción

| Servicio | Puerto | Proceso | Directorio |
|---|---|---|---|
| corillo-api | 3004 | uvicorn | `/home/corillo-adm/corillo-api/` |
| corillo-bot (chat) | 3001 | uvicorn | `/home/corillo-adm/corillo-bot/` |
| corillo-telegram | 3003 | uvicorn | `/home/corillo-adm/corillo-telegram/` |
| corillo-auth | 3002 | uvicorn | `/home/corillo-adm/corillo-auth/` |
| corillo-reel | — | python | `/home/corillo-adm/corillo-reel/` |
| PocketBase (corillo) | 8090 | pocketbase | `/home/corillo-adm/pocketbase/pb_data` |
| MediaMTX (HLS) | 8888 | mediamtx | — |
| MediaMTX (WebRTC) | 8889 | mediamtx | — |
| MediaMTX (RTSP interno) | 8554 | mediamtx | solo localhost |
| MediaMTX (API) | 9997 | mediamtx | — |
| corillo-thumbs | — | python3 | `scripts/thumb-gen.py` |
| thumbgen | — | bash | `/usr/local/bin/thumbgen-all.sh` |
| bitrate-monitor | — | python3 | `/home/corillo-adm/bitrate-monitor.py` |
| win-monitor | 8200 | uvicorn | `/home/corillo-adm/win-monitor/` |
| corillo-bf6-proxy | 3011 | node | `/opt/corillo/bf6-proxy/` |

Todos corren como systemd units. Para reiniciar: `sudo systemctl restart <nombre>`.

> **Otros servicios en el mismo servidor (no corillo):** `conteo.service` (portal financiero `conteo.marcossantiago.com`, puertos 8300+8095, repo `marcosstgo/conteo`), `gbn-mikrowisp.service` (puerto 8100), `openclaw.service` (AI gateway, puertos 18789+18791), `netdata.service` (monitoreo, puerto 19999). No tocar a menos que se sepa lo que se hace.

---

## Routing nginx

```
/api/bf6/*                → 3011  corillo-bf6-proxy
/api/*                    → 3004  corillo-api  (catch-all ^~, sin regex)
  /api/join               → 3003  corillo-telegram
  /api/admin              → 3003  corillo-telegram
  /api/telegram-webhook   → 3003  corillo-telegram
  /api/upload-vod         → 3004  (timeout 600s, sin buffering, max 3G)

/chat-api/*               → 3001  corillo-bot  (WebSocket, chat, digest, IA)

/live/*                   → 8888  MediaMTX HLS
/mediamtx-api/*           → 9997  MediaMTX HTTP API
/twitch-api/*             → 8880  Twitch proxy (inactivo al 2026-05-19)
/webrtc/*                 → 8889  MediaMTX WebRTC WHEP
/vods/reels/*             → /var/vods/reels/
/vods/*                   → /var/vods/live/
/assets/thumbs/*          → /var/www/stream/assets/thumbs/
/assets/kick/*            → /var/www/stream/assets/kick/
/overlay/bf6/*            → /opt/corillo/bf6-proxy/public/  (archivos estáticos)
/*                        → /var/www/stream/dist/  (Astro SSG)
```

Los canales (`/katatonia/`, `/tea/`, etc.) los captura la regex
`^/([a-z0-9][a-z0-9_]*)(/|$)` y nginx inyecta el key en
`player/index.html` via `sub_filter '__CHANNEL__'`.

### Otros dominios en el mismo nginx.conf

| Dominio | Backend | Notas |
|---|---|---|
| `conteo.marcossantiago.com` | `/var/www/conteo/` + proxy `/api/` → 8300, `/pb-conteo/` → 8095 | Repo: `marcosstgo/conteo` |
| `marcossantiago.com` | Docker 3010 | Repo: `marcosstgo/marcossantiago-web` |
| `kioskko.com` | Landing estática + Docker 4321 | — |
| `pagos.gbnsolutions.com` | gbn-mikrowisp 8100 | — |
| `pb.corillo.live` | PocketBase corillo 8090 | — |
| `uptime.corillo.live` / `status.corillo.live` | Proxy a 192.168.8.148:3001 | Red local |
| `vault.marcossantiago.com` | Proxy a 192.168.8.148:8080 | Red local |
| `oc.marcossantiago.com` | OpenClaw 18789 | — |

---

## corillo-api — Endpoints (`/api/`)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/streamers` | Roster completo activo con `avatar_url` desde PocketBase |
| GET | `/api/profile/{key}` | Perfil individual de un streamer |
| POST | `/api/regen-stream-key` | Regenerar stream key (autenticado) |
| GET | `/api/push-config` | Config VAPID para notificaciones push |
| POST | `/api/subscribe` | Suscribirse a notificaciones push de un canal |
| DELETE | `/api/subscribe` | Cancelar suscripción push |
| POST | `/api/internal/notify` | Disparar notificación push (uso interno) |
| GET | `/api/clip/{channel}` | Crear clip de 30s del live actual |
| GET | `/api/clip/vod/{vod_id}` | Crear clip de un VOD |
| POST | `/api/reel` | Crear reel (autenticado) |
| POST | `/api/reel/upload` | Subir video como reel (autenticado) |
| DELETE | `/api/reel/{id}` | Eliminar reel (autenticado) |
| PATCH | `/api/reel/{id}/visibility` | Cambiar visibilidad de reel |
| DELETE | `/api/vod/{id}` | Eliminar VOD (autenticado) |
| POST | `/api/upload-vod` | Subir VOD (autenticado, hasta 3G) |
| GET | `/api/health` | Health check |

---

## PocketBase — Colecciones principales

| Colección | Campos clave |
|---|---|
| `streamers` | `key`, `display_name`, `sub`, `bio`, `color`, `avatar`, `twitch`, `instagram`, `tiktok`, `stream_title`, `active`, `stream_key`, `upload_enabled` |
| `vods` | `channel`, `filename`, `title`, `duration`, `size`, `thumb`, `date`, `public` |
| `reels` | `channel`, `filename`, `title`, `duration`, `public` |
| `push_subscriptions` | `channel`, `endpoint`, `p256dh`, `auth` |

**Admin UI:** `https://pb.corillo.live`
**Credenciales:** en `/home/corillo-adm/corillo-api/.env`

> El campo nombre en PocketBase es `display_name`, no `name`.
> El endpoint `/api/streamers` lo mapea a `name` y computa `ava` (inicial).

---

## Frontend — Páginas

| URL | Archivo fuente | Descripción |
|---|---|---|
| `/` | `src/pages/index.astro` | Homepage: featured player, live rail, channel grid, VOD strip |
| `/{canal}/` | `src/pages/player/index.html` | Player universal (template con `__CHANNEL__`) |
| `/streamers/` | `src/pages/streamers/index.astro` | Directorio con stats en vivo y búsqueda |
| `/vods/` | `src/pages/vods/index.astro` | Browser de VODs filtrable por canal |
| `/vods/v/` | `src/pages/vods/v/index.astro` | Player de VOD individual |
| `/multiplayer/` | `src/pages/multiplayer/index.astro` | Vista multi-stream simultáneo |
| `/reels/` | `src/pages/reels/index.astro` | Grid de reels públicos |
| `/reels/v/` | `src/pages/reels/v/index.astro` | Player de reel individual |
| `/perfil/` | `src/pages/perfil/index.astro` | Dashboard del streamer (auth PocketBase) |
| `/join/` | `src/pages/join/index.astro` | Formulario de onboarding |
| `/roadmap/` | `src/pages/roadmap/index.astro` | Roadmap del proyecto |

---

## Layouts

| Archivo | Usado en |
|---|---|
| `src/layouts/SiteShell.astro` | Todas las páginas Astro (topbar, drawer, sidebar, footer) |
| `src/layouts/BaseLayout.astro` | Páginas sin sidebar |
| `src/layouts/FullscreenLayout.astro` | Embed fullscreen |
| `src/layouts/NoticiasPostLayout.astro` | Posts de noticias |

---

## Assets globales

| Archivo | Descripción |
|---|---|
| `public/assets/corillo.css` | Design system (tokens, componentes). Cache `?v=2` |
| `public/assets/homepage.css` | Layout homepage y topbar. Cache `?v=2` |
| `public/assets/player.js` | Lógica del player universal |
| `public/assets/streamers.js` | Fallback estático (`window.STREAMERS`) — backup si `/api/streamers` falla |
| `public/assets/styles.css` | Tokens CSS del player |

> Al modificar `corillo.css` o `homepage.css`, incrementar `?v=N` en todos
> los layouts que los cargan: `SiteShell.astro`, `BaseLayout.astro`,
> `FullscreenLayout.astro`, `perfil/index.astro`.

---

## Fuente de verdad de streamers

**PocketBase** es la fuente primaria. `/api/streamers` devuelve el roster con `avatar_url`.

`window.STREAMERS` (en `assets/streamers.js`) es fallback de emergencia si la API falla — no tiene `avatar_url`, solo letra inicial (`ava`).

**Para borrar un streamer:**
1. PocketBase → borrar o desactivar el record en colección `streamers`
2. `assets/streamers.js` → eliminar la línea correspondiente
3. Build + push

---

## Archivos fuera del repo (no versionados)

| Path | Descripción |
|---|---|
| `/home/corillo-adm/corillo-*/.env` | Variables de entorno de cada servicio |
| `/home/corillo-adm/corillo-*/*.db` | Datos runtime SQLite |
| `/home/corillo-adm/corillo-auth/*.pem` | Claves VAPID |
| `/home/corillo-adm/corillo-reel/.env` | Variables del reel bot — BOT_TOKEN, ALLOWED_USERS |
| `/home/corillo-adm/bitrate-monitor.py` | Desplegado por CI desde `scripts/bitrate-monitor.py` |
| `/usr/local/bin/thumbgen-all.sh` | Script de thumbnails alternativo — fuera del repo |
| `/var/vods/` | Grabaciones VOD y reels |
| `/var/www/stream/assets/thumbs/` | Thumbnails generados cada 60s |
| `/var/www/stream/assets/kick/` | Banners Kick del bitrate-monitor |
| `/home/corillo-adm/pocketbase/pb_data` | Datos PocketBase de corillo.live |

---

## Servicios — qué hace cada uno

### corillo-api (`api/server.py`) — Puerto 3004
API pública de la plataforma. Sin dependencias del chat ni Telegram.
- Roster de streamers con avatares desde PocketBase
- Perfiles individuales por canal
- Regeneración de stream keys
- Notificaciones push (VAPID): config, suscripción, envío
- Clips de 30s desde live o VOD
- Subida, borrado y visibilidad de reels
- Subida y borrado de VODs
- Health check

**Cache:** `/api/streamers` cachea el roster en memoria por 30 segundos (`STREAMERS_CACHE_TTL`).
Al añadir o borrar un streamer en PocketBase, el cambio tarda hasta 30s en aparecer en el sitio.
Para forzar actualización inmediata: `sudo systemctl restart corillo-api`.

### corillo-bot (`chat/server.py`) — Puerto 3001
Chat en vivo, IA y WebSocket. Solo responsabilidad: el chat.
- WebSocket por canal para mensajes en tiempo real
- Integración con LLM (Anthropic) — bot comenta el stream con visión
- Historial de mensajes persistido en SQLite
- Digest de resumen de chat
- Anti-spam y rate limiting

### corillo-telegram (`telegram/server.py`) — Puerto 3003
Telegram webhook, onboarding de streamers y notificaciones en vivo.
- Webhook de Telegram para comandos del bot
- Formulario `/join` — recibe solicitudes de nuevos streamers
- Aprobación/rechazo de streamers desde Telegram con botones inline
- Al aprobar: crea el record en PocketBase y se auto-actualiza en GitHub
- **Monitor de live** — polling a MediaMTX cada 15s, notifica al grupo de Telegram cuando un streamer nuevo va en vivo: `🔴 NOMBRE está en vivo · corillo.live/{canal}/`

### corillo-auth (`auth/server.py`) — Puerto 3002
Servicio minimalista de autenticación RTMP para MediaMTX.
- Una sola función: valida stream keys de publishers contra PocketBase
- MediaMTX llama a este endpoint antes de aceptar un stream entrante
- Cache de 60s por canal para no saturar PocketBase

### corillo-reel (`reel/bot.py`)
Bot de Telegram que descarga videos de redes sociales y los sube al servidor.
- Acepta URLs de Instagram, TikTok, YouTube Shorts, Twitter/X, Facebook
- Usa `yt-dlp` para la descarga y `ffmpeg` para procesamiento
- Solo usuarios en `ALLOWED_USERS` pueden usarlo
- **Corre en Docker**, parte del stack `/home/corillo-adm/marcossantiago-web/docker-compose.yml`
- Depende de `telegram-bot-api` container (misma red Docker) — no puede correr como systemd
- El CI copia `bot.py` a `/home/corillo-adm/corillo-reel/` y hace `docker compose build + up`
- Variables de entorno en el `.env` del stack `marcossantiago-web`

### corillo-thumbs (`scripts/thumb-gen.py`) y thumbgen (`thumbgen-all.sh`)
Dos servicios de thumbnails distintos que corren en paralelo:
- `corillo-thumbs.service` → `scripts/thumb-gen.py` — genera thumbnails de streams en vivo, los guarda en `/var/www/stream/assets/thumbs/`. **Versionado en el repo**, se despliega via CI.
- `thumbgen.service` → `/usr/local/bin/thumbgen-all.sh` — script bash alternativo de thumbnails. **No está en el repo**, instalado manualmente en el sistema.

### corillo-bf6-proxy — Puerto 3011

Proxy Node.js que sirve stats de Battlefield 6 desde gametools.network sin problemas de CORS.
- **Directorio:** `/opt/corillo/bf6-proxy/`
- **Endpoint proxy:** `GET /bf6/stats?name=JUGADOR&platform=PLATAFORMA`
- Llama a `https://api.gametools.network/bf6/stats/` y devuelve el JSON con `Access-Control-Allow-Origin: *`
- Caché en memoria de 5 minutos por jugador+plataforma
- Timeout de 12s hacia gametools — si falla devuelve JSON de error limpio
- Plataformas válidas: `ea`, `steam`, `psn`, `xbox`, `ps5`, `epic` (BF6 disponible en EA y Steam al 2026-06-05)

**Overlays estáticos** servidos en `/overlay/bf6/` desde `/opt/corillo/bf6-proxy/public/`:

| Archivo | URL pública | Tamaño OBS |
|---|---|---|
| `index.html` | `/overlay/bf6/` | Generador (no es overlay) |
| `overlay.html` | `/overlay/bf6/overlay.html?name=X&platform=Y` | 380×175 |
| `weapons.html` | `/overlay/bf6/weapons.html?name=X&platform=Y` | 380×255 |
| `accuracy.html` | `/overlay/bf6/accuracy.html?name=X&platform=Y` | 380×195 |
| `objective.html` | `/overlay/bf6/objective.html?name=X&platform=Y` | 380×225 |

> **Nota:** Las rutas `/api/bf6/` y `/overlay/bf6/` están en `/etc/nginx/nginx.conf` pero **NO en el `nginx.conf` del repo** — fueron agregadas directamente al servidor el 2026-06-05. Si el CI sobreescribe nginx.conf, hay que volver a agregar estos bloques. Pendiente: mover al repo.

### bitrate-monitor (`scripts/bitrate-monitor.py`)
Daemon que vigila el bitrate de los streams en vivo.
- Polling a MediaMTX cada `INTERVAL` segundos
- Si el bitrate supera `AUTO_KICK_KBPS`: alerta por Telegram, auto-kick via `ss -K`
- Lista `KICK_EXEMPT` de streamers exentos del kick (alertas siguen activas)
- Cooldown de 300s entre notificaciones para no spamear
- Notifica al recuperarse dentro del límite

---

## Scripts — referencia rápida

| Script | Cuándo usar |
|---|---|
| `scripts/vod-process.py` | Llamado automáticamente por MediaMTX al terminar un segmento grabado. Re-encodea a 5 Mbps, genera thumbnail, registra en PocketBase. No ejecutar manualmente. |
| `scripts/thumb-gen.py` | Daemon que genera thumbnails y previews de streams en vivo cada 60s. Corre como `corillo-thumbs.service`. |
| `scripts/vod-cleanup-short.py` | One-time: borra VODs con duración menor a un mínimo (limpieza de grabaciones cortas/fallidas). |
| `scripts/audit.sh` | Compara archivos críticos entre el repo y producción. Útil para detectar desincronías. |
| `scripts/pb-setup-vods.py` | One-time setup: crea la colección `vods` en PocketBase. |
| `scripts/pb-setup-reels.py` | One-time setup: crea la colección `reels` en PocketBase. |
| `scripts/pb-setup-push.py` | One-time setup: crea la colección `push_subscriptions` en PocketBase. |
| `scripts/pb-setup-vod-upload.py` | One-time: añade campo `upload_enabled` a la colección `streamers`. |
| `scripts/pb-add-stream-title.py` | One-time: añade campo `stream_title` a la colección `streamers`. |
| `scripts/pb-add-sub-field.py` | One-time: añade campo `sub` (categoría/status) a la colección `streamers`. |

> Los scripts `pb-setup-*` y `pb-add-*` son migraciones one-time. Ya están aplicados en producción — no volver a ejecutar.

---

## Convenciones de desarrollo

- **Editar siempre en `/var/www/stream/`** — es el working tree del repo
- `npm run build` para compilar Astro
- `git pull --rebase` antes de push (el CI hace commits automáticos de version bump)
- Cambios de nginx van en `nginx.conf` del repo — nunca editar `/etc/nginx/nginx.conf` directamente
- Cambios de API van en `api/server.py` — el CI los despliega automáticamente
- Nuevos endpoints en corillo-api no requieren cambios en nginx gracias al `^~ /api/` catch-all
