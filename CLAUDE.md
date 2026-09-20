# CLAUDE.md — corillo.live

Plataforma de streaming boricua (Aibonito, PR). Monorepo `marcosstgo/corillo`; el working tree
es `/var/www/stream/` y es **a la vez** el repo y lo que nginx sirve. Actualizado 2026-09-20.

## ⚠ Leer antes de tocar nada

1. **Nunca `npm run build` directo en `/var/www/stream`** — publica en vivo. Desplegar = `bash scripts/deploy-corillo.sh`
   (respalda `dist`, compila, revierte si falla; conserva los 3 últimos `dist.bak-*`).
   Para solo comprobar que compila: `npx astro build --outDir <dir-temporal>`.
2. **Un push a `main` dispara CI** (`.github/workflows/deploy.yml`): rsync con `--delete` de todo el repo, y además copia al servidor `telegram|api|auth|chat|reel`, `scripts/vod-process.py`, `bitrate-monitor.py`, `nginx.conf` y `mediamtx.yml` (y **reinicia MediaMTX y nginx si cambian**).
   - **Reconciliado el 2026-09-20:** el repo estaba atrasado respecto a producción (sin `POST /register`, sin el arreglo `_low` de MediaMTX, sin los vhosts de pabarranquitas/pueblospr). Se copió producción → repo en `telegram/server.py`, `api/server.py`, `mediamtx.yml`, `nginx.conf`. La versión anterior del repo (incl. el clip con VAAPI de `api/server.py`) está en `~/backups-corillo-2026-09-20/`.
   - El rsync ahora **excluye** `/pabarranquitas`, `/pueblospr`, `/ruta-preview-hub` (otros proyectos servidos desde aquí, con su propio `.git`), `/dist.bak-*` y `/.claude`. Comprobado con un `rsync --dry-run`: antes borraba 154+42 archivos de esos proyectos y los 3 respaldos de `dist`; ahora solo recambia `dist/_astro`.
   - **Regla nueva:** si cambias algo directamente en producción (`/etc/nginx`, `/etc/mediamtx`, `~/corillo-*/server.py`), cópialo también al repo en el mismo momento; si no, el próximo push lo pisa. Comprobación rápida: `diff` de esos 4 archivos contra producción.
   - `mediamtx.yml` invoca `/usr/local/bin/corillo-{rtc-start,stream-up,notify}.sh`, que **no están en ningún repo** (copia en `~/backups-corillo-2026-09-20/`).
3. El remote `origin` de este repo lleva un token de GitHub embebido en la URL. No imprimir `git remote -v`; pendiente sacarlo.
4. Rama actual del working tree: `feat/senal-home`. El rediseño de sep-2026 está en producción pero **sin push a GitHub**.

## Stack
Astro **7.3.3** estático (`output:'static'`, `trailingSlash:'always'`, `format:'directory'`) · Node 22 · sitemap+RSS por integración ·
servicios Python/FastAPI · PocketBase · MediaMTX · nginx · Ubuntu 24.04. Solo hay 3 dependencias npm. Rendimiento medido 2026-09-20 (móvil 4G lento, CPU x4): inicio FCP 0.8 s, LCP 0.8 s, CLS 0.04; nginx sirve HTTP/2 + gzip (sin brotli), CSS/JS 1 h, fuentes 6 meses. Pendiente de rendimiento: Font Awesome completo (100 KB css + 156 KB fuente) para ~20 íconos.

## Mapa del frontend (`src/`)
- `layouts/SiteShell.astro` — shell de casi todas las páginas. **Navegación estilo Kick** (`public/assets/shell.css`, clases `nv-*`): barra superior fija (logo, búsqueda, Entrar/Crear cuenta o avatar) + menú lateral grande con fichas de color (Explorar / Más, contador "en vivo" junto a Streamers y tarjeta Crear canal / Mi canal), colapsable a íconos (`localStorage corillo-sb`), en escritorio; en móvil, barra inferior de 5 pestañas y el menú pasa a cajón ("Más"). La lista de canales ya NO está en el menú (vive en `/streamers/`). La sesión se lee de `localStorage.pocketbase_auth` sin cargar el SDK. Carga `corillo.css`, `homepage.css`, `senal-home.css`, `site2.css`, `shell.css`; **fuerza `data-theme=dark`**.
  `FullscreenLayout` → `reels/`, `reels/v/`. `NoticiasPostLayout` → `noticias/[slug]`.
  Sin layout (HTML propio): `player/`, `perfil/`, `embed/v/`; `perfil` y `reels` cargan `legacy-type.css` (Bricolage/DM Sans, sin mayúsculas espaciadas). VODs: selector 2/1 columnas (`localStorage corillo-vods-cols`).
- `pages/`: `index`, `streamers`, `vods`, `vods/v`, `multiplayer`, `reels`, `reels/v`, `perfil`(+`reset`), `player`, `join`, `verificar`,
  `configuracion`, `faq`, `legal`, `dmca`, `que-es-corillo`, `roadmap`, `software`, `noticias`(+`[slug]`), `embed/v`, `rss.xml.js`.
- `content/noticias/*.md` — content collection (schema en `content.config.ts`); un post nuevo = un `.md`.
- CSS por página (en `public/assets/`): `home2.css`, `streamers2.css`, `vods2.css` (rediseño); `site2.css` = shell global y tokens `--h2-*`;
  `corillo.css` = framework `crl-*` heredado; `homepage.css`/`senal-home.css`/`styles.css` = legado, no crecer.
  Al cambiar un CSS con `?v=N` fijo, subir `N` en el `<link>` que lo carga.
- Páginas `p-legacy` (14 de contenido): capa tipográfica que remapea `--crl-display/--crl-mono`. Astro añade `[data-astro-cid-*]`
  a sus estilos, así que los overrides comunes usan prefijo `body`.
- Identidad (desde 2026-09-20): **paleta Cobalto** — fondo azul bandera `#06143f`, acento flamboyán `#ff6a3d`, acento 2 sol `#ffd23f`, en vivo `#ff2d55`. Tokens en 2 sitios: `--crl-*` en `corillo.css` `:root` y `--h2-*` en `site2.css` (los nombres `--h2-cyan`/`--h2-mag` son históricos: hoy son acento y acento 2); `--h` (matiz oklch) en `homepage.css`. Los degradados sobre video usan `--crl-ink-rgb`. El aro acento→acento 2 solo marca "en vivo". Evitar estética gamer.
- Skeletons de carga: clases `sk*` en `site2.css`; el HTML estático los lleva y el JS los reemplaza con `innerHTML`.
- Roster: PocketBase manda (`/api/streamers`); `public/assets/streamers.js` es solo fallback y además **valida las keys del player**
  (una key que no esté ahí cae en `/_404/`).

## Registro / correo (verificar antes de tocar)
Registro autoservicio: `/join/` → `POST /api/register` (telegram-service :3003, código solo en producción) crea la cuenta en PocketBase (`active:false`) y pide el correo; el enlace lleva a `/verificar/?token=` que llama `confirm-verification`; el hook `pb_hooks/activate_on_verify.pb.js` la activa. Correo por Mailgun (`noreply@mg.corillo.live`, SPF/DKIM ok).
**BUG ABIERTO (2026-09-20):** las plantillas de la colección `streamers` usan marcadores que PocketBase 0.36.7 no reemplaza (`{{.Token}}`, `{{"{{"}.ActionUrl…}}`; esta versión solo entiende `{TOKEN}`, `{ACTION_URL}`, `{APP_URL}`). Resultado: el correo de verificación y el de reseteo salen con enlace roto; en el log de PB, las 2 confirmaciones registradas fallaron (`Missing email token claim`). Corrección pendiente de aprobar: verificación → `https://corillo.live/verificar/?token={TOKEN}`; reseteo → `https://corillo.live/perfil/reset/?token={TOKEN}`. Respaldar la colección antes.

## Reels, miniaturas y perfil (2026-09-20)
- **Reels** (`/reels/`, `src/pages/reels/index.astro` + `public/assets/reels2.css`): visor vertical inmersivo (imán vertical, autoplay,
  progreso con scrub, teclado ↑↓ espacio M, enlace directo `?r=<id>`). Los **directos aparecen primero** en el feed y cada clip lleva a
  `/vods/v/?id=<vod_id>&t=<start_sec>` (la página de VOD entiende `?t=`). Carga rápida: usa `<nombre>_720.mp4` / `_480.mp4` según la conexión,
  baja sola a 480p si se traba, precarga el siguiente y cachea la lista en `localStorage rl_cache_v1`. Si no existe la versión liviana cae al original.
- **Versiones livianas**: `scripts/reel-variants.py` (idempotente). La API (`api/server.py`) lo lanza en segundo plano al crear un reel y borra las
  variantes al borrarlo. Para reels viejos: `python3 scripts/reel-variants.py`.
- **Miniaturas/previews**: `scripts/thumb_crop.py` detecta barras negras (solo arriba/abajo) y deja 1280×720 sin deformar. Lo usan `thumb-gen.py` (directos,
  servicio `corillo-thumbs`) y `vod-process.py` (copia inline; se despliega suelto). `scripts/regen-thumbs.py [--previews]` regenera las existentes.
  Las miniaturas se sirven 7 días: al cambiar su formato, subir el `?v=N` en las plantillas (hoy `?v=2`).
- **Perfil** (`/perfil/`): layout de creador con barra lateral en `public/assets/perfil2.css` (cargado tras el CSS propio de la página, que va `is:inline`
  para conservar el orden). El HTML envuelve hero+pestañas+paneles en `.pf-layout`.
- **Selector 2/1 columnas** en `/vods/` (`corillo-vods-cols`) y `/streamers/` (`corillo-streamers-cols`).
- **Overlays** (`/overlay/bf6/`, repo aparte `marcosstgo/corillo-bf6-overlays`, servido desde `/opt/corillo/bf6-proxy/public`): tema `ov-theme.css`,
  generador nuevo y WARDOGS (ver el CLAUDE.md de ese repo). WARDOGS no tiene API pública de perfiles; el de perfil necesita `STEAM_API_KEY`.

## Trampas de Astro 7 / player
- `<script src={expr}>` sin `is:inline` **se descarta en silencio** (el build dice "Complete"). Todos los de `player/index.astro` son `is:inline`.
- `/{canal}/` lo sirve nginx con `sub_filter '__CHANNEL__'` sobre `player/index.html`: ese HTML debe conservar `__CHANNEL__` y sus 4 scripts externos.
- Tras un upgrade mayor: comparar `<script>/<link>` por página entre `dist` viejo y nuevo. Un timeout en una ruta con video es una falla, no un artefacto.

## 🚫 No leer completos (usar Grep, o Read con `offset`/`limit`)
`public/assets/hls.min.js` (414 KB, una línea) · `package-lock.json` · `public/assets/fontawesome/` · `public/assets/pocketbase.umd.js` ·
`public/assets/streamer-pro/` (18 MB binarios) · `dist*/` · `node_modules/`.
Grandes pero editables: `src/pages/perfil/index.astro` (2960 líneas) · `public/assets/corillo.css` (2220) · `public/assets/player.js` (1271) ·
`src/pages/index.astro` (851). `public/corillo-css/index.html` y `public/streamer-pro/index.html` son documentación/landing estática de ~80–90 KB.

## Carpetas de otros proyectos que viven aquí (fuera de git, en `.gitignore`)
`pabarranquitas/` (pabqtas, `/app` lo sirve nginx), `pueblospr/` (`registro/`, `panel/`; `pueblospr-pb.service` usa `pb_migrations`),
`ruta-preview-hub/`, `assets/kick/`. **No mover ni borrar**: producción las usa. Cada una tiene su README/CLAUDE.md.
Como están en `.gitignore`, Grep/Glob no las ven; usar `rg --no-ignore` con la ruta explícita si hay que trabajar ahí.
Material suelto que había en la raíz (capturas, zips, PDFs, propuestas) se archivó en `/home/corillo-adm/archivo-corillo-raiz/`.

## Documentación de detalle (leer solo si hace falta)
| Archivo | Contenido |
|---|---|
| `docs/infra.md` | servicios y puertos, routing nginx, endpoints de `corillo-api`, colecciones PocketBase, archivos fuera del repo, qué hace cada servicio, scripts, pipeline de CI |
| `docs/astro-mejoras-plan.md` | plan por fases de Astro; hechas 0, 1, 1b, 3; pendientes 2, 4, 5 |
| `docs/MIGRATION.md` | mover la plataforma a otro servidor |
| `docs/PROJECT_NOTES.md` | histórico may-2026 (VOD re-encode, Corillo CSS, SEO); no vigente |

## Convenciones
- Editar en `/var/www/stream/`; cambios de nginx en `nginx.conf` del repo (y aplicar al vivo con backup + `nginx -t` antes de reload: es un único archivo monolítico).
- Cambios de API en `api/server.py` (el CI los despliega y reinicia el servicio); nuevos endpoints no requieren nginx (`^~ /api/`).
- `git pull --rebase` antes de push (el CI hace commits de version bump).
- Servicios: `sudo systemctl restart <nombre>`. Datos y `.env` de cada servicio en `/home/corillo-adm/corillo-*/` (no versionados).
