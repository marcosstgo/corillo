# Rediseño de corillo.live — noviembre 2026

Propuesta para la vuelta de corillo.live después de la muerte del disco (28-oct-2026). Escrita el 30-oct a pedido de
Marcos: "me gustan esos colores, me gusta cómo está, pero quiero darle un nuevo look… la opción de streaming tiene que
estar porque es una plataforma de streaming". Este documento se aprueba **antes** de tocar el código de la portada.

## 1. El problema

La portada de septiembre (Cobalto) es buena cuando hay alguien en vivo: nombre gigante a sangre, rostros, VODs en
formato editorial. Pero está construida sobre el video, y hoy no hay video grabado (los 97 VODs y 19 reels murieron con
el disco). Sin nadie en vivo, la primera pantalla entera dice que no hay nada: título gigante "Sin transmisión",
"Todos los canales están fuera de línea", botón "Ver VODs" hacia una página vacía, y "Ponte al día" sin contenido.
La mayor parte del día nadie está en vivo, así que esa es la portada que casi todo el mundo ve.

Mientras tanto Corillo sí tiene vida todos los días: una noticia nueva cada mañana, ofertas cada hora, juegos gratis
cada semana, 30 personas conectadas en el Discord a cualquier hora, el Bochinchero, el Mercado, los panas con sus perfiles.
Nada de eso está en la portada (salvo "Gratis esta semana", abajo del todo).

## 2. La idea

**Corillo deja de ser "una parrilla de streams" y pasa a ser la portada del corillo**: el lugar donde un gamer boricua
entra a ver qué está pasando hoy. Tres pulsos, en este orden de importancia:

1. **En vivo** — el corazón. Cuando alguien prende, se apodera de la portada como hoy (eso no cambia).
2. **Hoy** — información: la noticia del día, juegos gratis, ofertas que valen la pena, equipo con envío a PR.
3. **El corillo** — la gente: los panas (streamers), quién está en el Discord ahora y en qué sala, el Bochinchero,
   el Mercado entre boricuas.

La portada nunca dice "no hay nada". Si nadie está en vivo, abre con la noticia del día y con lo que está pasando en
el Discord (que es actividad real, de personas reales, ahora mismo).

## 3. Lo que NO cambia (identidad)

- Paleta Cobalto: fondo `#06143f`, superficies `#0d2260` / `#173383`, texto hueso `#f5f8ff`, apagado `#a4b6e6`,
  flamboyán `#ff6a3d`, sol `#ffd23f`, en vivo `#ff2d55`, verde `#35e0a1`.
- **El degradado flamboyán → sol es solo para "en vivo".** Todo lo demás, hueso sobre azul.
- Bricolage Grotesque 800 para títulos (sin MAYÚSCULAS espaciadas), DM Sans para el texto, logo C◎RILLO.
- La portada es sobre las personas. Nada de estética gamer (retículas, neón, HUD).
- La navegación estilo Kick (barra arriba + menú lateral + pestañas en el celular).

## 4. Lo que cambia

### 4.1 La portada (de arriba a abajo)

| # | Sección | Con alguien en vivo | Sin nadie en vivo |
|---|---|---|---|
| 1 | **Arriba** | El stream a sangre con el nombre gigante (como hoy) + "también en vivo" | **Portada del día**: fecha, la noticia del día a tamaño titular, y al lado la tarjeta **"El corillo ahora"** (gente en el Discord, salas activas y a qué juegan, último en vivo) |
| 2 | **Los panas** | Rostros; los que están en vivo primero con el aro de en vivo | Rostros con su línea ("Design · Corillo DEV") y "Crear tu canal" al final |
| 3 | **Hoy en Corillo** | Noticias: una grande + tres + lista corta. Tarjetas tipográficas con el color de su categoría (no hay fotos, y no hacen falta) | igual |
| 4 | **Gratis y a precio de pana** | Juegos gratis (con cuánto falta para que se acaben) + las mejores rebajas + equipo con envío a PR | igual |
| 5 | **El Bochinchero** | Banda propia: qué es, botones para oír sus voces (los mp3 reales), "Añádelo a tu server" | igual |
| 6 | **Mercado** | Últimos anuncios; si no hay, invitación a vender ("véndele tu equipo a otro boricua") | igual |
| 7 | **¿Tienes algo que transmitir?** | CTA para crear canal (como hoy) | igual |

### 4.2 Navegación

- **Explorar**: Inicio · En vivo (con el contador) · Noticias · Ofertas · Mercado · Comunidad (Discord).
- **Herramientas**: Bochinchero · Overlays · Software · Equipo (hoy `/equipo/` no tiene enlace).
- **Corillo**: Sobre Corillo · Roadmap.
- **VODs y Reels salen del menú** hasta que haya material; vuelven solos cuando PocketBase tenga registros.
  Multiplayer sale del menú y aparece solo cuando hay 2+ en vivo.
- **Celular** (5 pestañas): Inicio · En vivo · Noticias · Ofertas · Más.

### 4.3 Contenido

- Noticias: la categoría "Puerto Rico" tiene 0 notas: `daily-news.py` debería incluir fuentes de PR.
  Retirar o archivar las 7 notas viejas que hablan de VODs y reels.
- Ofertas y Mercado se compilan con el sitio: el VPS los genera y dispara un deploy hook de Cloudflare Pages.
- Los textos de RTMP pasan a `rtmp://media.corillo.live/live` (8 lugares).

## 5. Plan técnico (cuando se apruebe el diseño)

1. **Un solo juego de colores**: hoy hay tres (`--crl-*`, `--h2-*`, alias de `homepage.css`/`styles.css`). Se deja uno.
   `homepage.css` (38 KB) y `senal-home.css` dejan de cargarse en todas las páginas.
2. **URLs en un solo lugar** (`src/data/site.ts`): `API = https://api.corillo.live`, `MEDIA = https://media.corillo.live`,
   `PB = https://pb.corillo.live`. Hoy hay rutas relativas `/api/`, `/live/`, `/mediamtx-api/`, `/assets/thumbs/`
   repartidas en ~20 archivos y en Cloudflare Pages no existirían.
3. **Canal `/{key}/`**: en el server viejo lo armaba nginx (`sub_filter __CHANNEL__`). En Pages: una Function pequeña
   o generar una página por canal al compilar.
4. Portada nueva en `src/pages/index.astro` + `public/assets/home3.css`; se borra el código muerto (ticker, stats).
5. Font Awesome completo (~400 KB) → solo los íconos usados.
6. Medir de nuevo (FCP/LCP/CLS en móvil 4G lento): la meta es no empeorar el 0.8 s de septiembre.
7. Español primero; los textos nuevos de la portada van a `src/i18n/es.json` para que el inglés sea fácil después.

## 6. Ideas para después (no entran en esta vuelta)

- **Agenda**: streams programados y torneos del corillo ("hoy a las 9 PM: Kata en BF6").
- **Portadas para las noticias** generadas con su categoría (como las tarjetas OG de ofertas).
- El Bochinchero leyendo la noticia del día y las ofertas por voz en el Discord (ya está en su roadmap).
- Resumen semanal por correo (Mailgun ya está montado).
