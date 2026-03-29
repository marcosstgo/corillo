# Project Notes

## Estado actual
- `Corillo CSS` va por `v1.4.0`.
- El framework ya documenta y expone componentes reales usados por el producto.
- `sitemap.xml` y `robots.txt` ya existen y el sitemap ya fue enviado a Google Search Console.

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
