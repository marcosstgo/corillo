# Project Notes

## Estado actual
- `Corillo CSS` va por `v1.4.0`.
- El framework ya documenta y expone componentes reales usados por el producto.
- `sitemap.xml` y `robots.txt` ya existen y el sitemap ya fue enviado a Google Search Console.

## 2026-05-13 — VOD pipeline: re-encode automático

### Problema
- VODs subían/grababan con bitrate intacto del source (15-20 Mbps porque OBS transmite a ese bitrate). En playback web causaba buffering en conexiones <16 Mbps sostenidos.
- Tanto el endpoint manual (`/chat-api/upload-vod`) como las grabaciones automáticas de MediaMTX (`vod-process.py`) hacían `ffmpeg -c copy -movflags +faststart` — sin re-encodear.

### Fix
- **`api/server.py`** (endpoint `/upload-vod`): re-encode con `libx264 preset fast`, CRF 23, cap `5 Mbps` + `bufsize 10M`, scale a 1920×1080 max (downscale-only), profile high level 4.0, pix_fmt yuv420p, AAC 128k, faststart. Timeout subido a 1800s.
- **`scripts/vod-process.py`** (hook MediaMTX): mismo encode pero `preset faster` (más rápido para batch automatizado). Timeout dinámico `max(3600, duration*8)s`. Función renombrada `remux_faststart` → `transcode_web_optimized`.
- Aplica a TODOS los canales (no solo marcos).

### Batch retroactivo
- Re-encodeados los 8 VODs de `marcos` que estaban a 15-16 Mbps → 4.6-5.0 Mbps.
- **Total**: 1358 MB → 401 MB (ahorro ~957 MB).
- Backups en `/var/vods/live/marcos/*.orig.mp4` (~1.4 GB; borrar cuando Marcos confirme calidad).
- VODs de `katatonia` quedaron como están (ya estaban a ~6 Mbps; ahorro marginal no justifica ~75 min de CPU). Próximos streams sí saldrán a 5 Mbps automáticamente.

### Para subir el listón a "bulletproof"
HLS adaptativo (3 calidades + master `.m3u8`) está pendiente. Esto resolvería el último 10-20% de viewers en conexiones móviles malas. Estimado: 3-4 horas de trabajo (re-encode multi-variant + actualizar el player de `/vods/v/` para hls.js).

### Archivos huérfanos detectados
- `/var/vods/live/marcos/2026-03-23_*.mp4` (9 archivos, ~3.2 GB total) — no están en PocketBase. Probablemente test recordings viejas. Marcos puede confirmar si borrar.

## Corillo CSS
- Archivo base: `/assets/corillo.css`
- Docs: `/corillo-css/index.html`
- Estado actual de docs:
  - version `v1.4.0`
  - `48 componentes`
  - peso aproximado `61.06 KB` y `10.97 KB gz`

### Componentes recientes
- `crl-stream-card`
- `crl-page-header`
- `crl-filter-panel`
- `crl-gallery`
- `crl-empty-hero`
- `crl-stat-grid`
- `crl-player-shell`
- `crl-chat-panel`
- `crl-player-dropdown`
- `crl-player-rail`
- `crl-player-vods`

### Dirección del framework
- El API oficial debe seguir moviéndose a `crl-*`.
- Los aliases sin prefijo pueden quedarse solo por compatibilidad temporal.
- `styles.css` debe considerarse legacy y no seguir creciendo.

## Páginas y cambios importantes

### Home
- Tiene toggle de theme en nav y drawer.
- Usa `localStorage` con la key `corillo-theme`.
- Se corrigió el logo para que invierta en light mode.
- Se ajustó contraste en nav, sidebar, drawer y footer para light mode.
- Desde 2026-05-12 el home usa el layout compartido `SiteShell` (drawer + sidebar + topbar + footer). Antes tenía el menú inline duplicado.

### Layout compartido — `SiteShell`
- Archivo: `src/layouts/SiteShell.astro`. Documentación completa en `CLAUDE.md` → "Layout system".
- Reemplaza a `BaseLayout` + `LiveSidebar` (ambos deprecated). Todas las páginas de contenido lo usan: home, vods, streamers, multiplayer, noticias, software, roadmap, faq, que-es-corillo, legal, dmca, join, configuracion, perfil/reset, vods/v, y los posts de noticias vía `NoticiasPostLayout`.
- No lo usan (intencional): `player/` (nav por canal), `perfil/` (dashboard propio), `reels/` y `reels/v/` (fullscreen 9:16), `embed/v/` (iframe).
- Buscador del topbar despacha el evento `crl-search`; la página activa lo escucha para filtrar su contenido (hoy solo el home filtra el grid de canales).

### Sobre Corillo
- Página: `/que-es-corillo/`
- Enfoque humano y boricua.
- Debe dejar claro que el proyecto nace en Aibonito, Puerto Rico.
- El texto importante incluye: referencias, lenguaje y prioridades nuestras.
- Se enfatizó que por ahora la entrada es por invitación.
- Tiene un detalle pequeño de bandera con azul de Corillo, no una bandera grande.

### Roadmap / FAQ / Multiplayer / Player
- Se hicieron varias correcciones de light mode.
- Branding SVG ya responde al tema claro/oscuro.
- `multiplayer` ya usa varios componentes reales de `Corillo CSS`.
- `player` ya migró parte importante del shell al framework.

### Player
- Se migraron al framework:
  - nav shell
  - chat panel
  - dropdown
  - player rail
  - player vods
- Se corrigió un bug de `chat-hidden` tras la migración al framework.
- Se reforzó el refresco visual del botón de notificaciones.
- WebRTC tuvo un ajuste de tolerancia en `disconnected` para no caer demasiado rápido.
- Ese cambio es razonable y seguro de dejar, pero no debe venderse como fix definitivo de backend.

## SEO
- Pasada SEO hecha en páginas públicas principales.
- Se añadieron o completaron:
  - `meta description`
  - `og:*`
  - `twitter:*`
  - `canonical`
- Páginas tocadas:
  - `/streamers/`
  - `/multiplayer/`
  - `/vods/`
  - `/roadmap/`
  - `/faq/`
  - `/join/`
  - `/que-es-corillo/`
  - `/software/`
  - `/corillo-css/`

## Sitemap
- Actual actual: sitemap simple.
- Para el tamaño actual del sitio, eso es suficiente.
- A futuro se puede automatizar la generación del sitemap.
- `sitemap-index.xml` sería opcional más adelante cuando el site crezca más.

## Navegación
- `Sobre Corillo` ya fue añadido en varias páginas principales.
- El nombre acordado para el enlace es `Sobre Corillo`.

## Notas operacionales
- Si aparece un bug raro luego de migrar una vista a `Corillo CSS`, revisar primero si la lógica JS todavía depende de clases viejas que ya no tienen estilo.
- En el player, varias regresiones recientes vinieron exactamente de esa clase de desalineación entre JS y framework.

## Próximos pasos naturales
- Seguir puliendo el `player` dentro de `Corillo CSS`.
- Seguir reduciendo CSS local en páginas grandes.
- Eventualmente trabajar `crl-site-footer v2` y `corillo-ui.js` opcional.

## Noticias
- Nueva sección pública en /noticias/.
- Primeras notas estáticas:
  - /noticias/corillo-css-v1-4/
  - /noticias/sobre-corillo/
  - /noticias/player-y-seo/
- Enlace añadido en home para hacerla visible desde navegación y footer.



  - /noticias/la-fiebre-puerto-rico/.

## Validacion de keys del player y rutas falsas indexadas

Se añadió una defensa para evitar que URLs raras se conviertan en canales ficticios dentro del player.

Cambios hechos:
- ssets/player.js ahora valida el channel key antes de iniciar el player.
- El key debe cumplir el formato ^[a-z0-9_]{1,32}$.
- El key no puede ser una ruta reservada como live, webrtc, chat-api, ods, 
oticias, etc.
- El key además debe existir en window.STREAMERS (ssets/streamers.js).
- Si no pasa esa validación, redirige a /_404/.
- 
ginx.conf rechaza rutas cuyo primer segmento parece archivo (por ejemplo index.m3u8) para que no entren al template del canal.
- obots.txt bloquea rutas técnicas como /live/, /webrtc/ y APIs para reducir indexación basura.

Por qué se hizo:
- Google llegó a indexar URLs falsas tipo index.m3u8 como si fueran páginas de canal.
- El problema venía de tratar cualquier primer segmento válido como key de canal.

Impacto esperado:
- Los streamers actuales no deben afectarse porque sus keys ya viven en ssets/streamers.js y usan el formato permitido.
- Las futuras keys tampoco deberían tener problema si siguen la convención actual: minúsculas, números y _, y se añaden al roster antes de usarse públicamente.

Riesgo principal a recordar:
- Si en el futuro se crea un streamer nuevo y su key no se añade a ssets/streamers.js, la ruta del canal caerá en /_404/ aunque el backend o Twitch ya exista.
- Si en algún momento quieren permitir otro formato de key (por ejemplo guion -), habrá que actualizar esta validación primero.
