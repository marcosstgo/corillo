# MIGRATION.md

## Migrar CORILLO a otro servidor

Esta guía resume lo necesario para mover la plataforma completa a un servidor nuevo sin depender de memoria o pasos sueltos.

## Panorama general

CORILLO no es solo un sitio estático.

La plataforma tiene dos capas:

1. Capa web
- HTML estático
- CSS / JS
- assets, sitemap, robots, PWA

2. Capa de infraestructura
- Nginx
- MediaMTX
- PocketBase
- servicios Python (`api`, `auth`, `chat`, `telegram`)
- thumbnails y pipeline de VODs
- systemd

Mover la capa web es fácil.
Mover la plataforma completa requiere preparar bien la infraestructura.

## Qué sí se mueve fácil

Desde este repo se mueve bien:
- `/var/www/stream/` completo
- páginas públicas
- `assets/`
- `player/`, `multiplayer/`, `streamers/`, `vods/`, `noticias/`
- `corillo.css` y documentación del framework
- `sitemap.xml`, `robots.txt`, `manifest.json`, `sw.js`
- configs versionadas como `nginx.conf`, `Caddyfile`, `mediamtx.yml`

## Qué requiere atención especial

Estas piezas son las más delicadas:
- Nginx y sus rutas proxy
- MediaMTX y auth hook RTMP
- PocketBase y su data real
- variables de entorno de servicios Python
- permisos en `/var/vods/`
- servicio de thumbnails
- script vivo de VODs fuera del repo

## Dependencias principales

El servidor destino debe tener al menos:
- Ubuntu Server o distro equivalente
- Nginx
- MediaMTX
- PocketBase
- Python 3.12+
- ffmpeg
- systemd
- SSL funcionando

## Estructura esperada

Rutas clave actuales:
- Web root: `/var/www/stream/`
- VODs: `/var/vods/`
- MediaMTX config: `/etc/mediamtx/mediamtx.yml`
- VOD script vivo: `/home/corillo-adm/corillo-vod/vod-process.py`
- Servicios Python: directorios propios bajo `/home/corillo-adm/`

## Orden recomendado de migración

### 1. Preparar servidor base

Instalar:
- Nginx
- MediaMTX
- PocketBase
- Python
- ffmpeg

Crear usuario operativo, por ejemplo:
- `corillo-adm`

### 2. Copiar el sitio

Copiar este repo al nuevo web root:
- `/var/www/stream/`

Si usas Git:
- clonar repo
- checkout a la rama correcta

## 3. Configurar Nginx

Tomar como base [nginx.conf](/c:/corillo/nginx.conf).

Verificar que funcionen estas rutas:
- `/mediamtx-api/`
- `/live/{key}/index.m3u8`
- `/vods/{channel}/{filename}`
- fallback del player universal
- service worker y assets estáticos

## 4. Configurar MediaMTX

Tomar como base [mediamtx.yml](/c:/corillo/mediamtx.yml).

Verificar:
- RTMP ingest
- HLS output
- auth hook hacia `auth/server.py`
- recording habilitado
- `runOnRecordSegmentComplete`
- ruta `_rtc` si se usa WebRTC

## 5. Migrar PocketBase

Hay que mover la base de datos real y archivos relacionados.

Sin PocketBase:
- auth de perfiles no funciona
- stream keys no validan
- perfiles públicos pueden romperse
- VOD metadata no aparece

## 6. Levantar servicios Python

Servicios a revisar:
- `api/server.py`
- `auth/server.py`
- `chat/server.py`
- `telegram/server.py`
- scripts auxiliares de thumbs / VOD

Importante:
- revisar puertos
- revisar `.env`
- revisar hosts internos
- revisar tokens y secretos

## 7. Restaurar systemd services

Servicios actuales importantes:
- `mediamtx.service`
- `nginx.service`
- `pocketbase.service`
- `corillo-api.service`
- `corillo-auth.service`
- `corillo-bot.service`
- `corillo-telegram.service`
- `corillo-thumbs.service`

Conviene exportar o recrear sus unit files en el nuevo servidor.

## 8. VOD pipeline

Este punto necesita cuidado.

Según [CLAUDE.md](/c:/corillo/CLAUDE.md), el script vivo de VODs corre fuera del repo:
- `/home/corillo-adm/corillo-vod/vod-process.py`

Eso significa que copiar solo el repo no basta.

Hay que:
- copiar también ese script vivo
- verificar su venv
- verificar permisos de escritura en `/var/vods/`
- probar thumbnails y preview MP4

## 9. Permisos

Revisar especialmente:
- `/var/www/stream/`
- `/var/vods/`
- logs de servicios
- usuario que ejecuta `vod-process.py`
- usuario que crea grabaciones desde MediaMTX

## 10. DNS y SSL

Actualizar:
- DNS del dominio
- certificados SSL
- cualquier webhook externo que dependa del hostname

Especial atención a:
- Telegram webhook
- rutas absolutas en metadata y SEO

## Checklist de validación

Después de migrar, probar esto:

### Sitio público
- Home carga
- theme toggle funciona
- logos cargan bien
- `Noticias` carga
- `Roadmap`, `FAQ`, `Sobre Corillo` cargan

### Streaming
- RTMP entra
- HLS sale en `/live/{key}/index.m3u8`
- player universal abre un canal
- multiplayer detecta canales en vivo
- viewer count responde

### Backend
- auth de perfil funciona
- stream key valida
- chat funciona
- Telegram webhook responde
- thumbnails se generan

### VODs
- se graba un stream nuevo
- se crea thumbnail
- se crea preview clip
- aparece VOD en PocketBase
- el player offline puede usar el último VOD

### SEO / estáticos
- `/sitemap.xml` carga
- `/robots.txt` carga
- `manifest.json` carga
- `sw.js` responde

## Qué tan difícil es realmente

### Fácil
- mover la web estática
- mover CSS, páginas y assets

### Media
- mover Nginx + MediaMTX + servicios

### Lo más delicado
- PocketBase
- secrets
- systemd
- VOD pipeline y permisos

## Qué mejoraría esta migración en el futuro

Para que mover la plataforma sea más fácil, convendría:
- versionar unit files de systemd dentro del repo
- tener un `.env.example` por servicio
- documentar puertos y secretos en un solo lugar
- eliminar pasos manuales del VOD processor
- crear un script de bootstrap para servidor nuevo
- tener un `DEPLOY.md` separado del contexto general

## Conclusión

Sí, CORILLO se puede mover a otro servidor.

La parte web ya está bastante portable.
Lo que requiere más disciplina es la infraestructura alrededor del streaming, auth, PocketBase y VODs.

La buena noticia es que no parece una plataforma atada de forma peligrosa al servidor actual. Lo que falta es seguir convirtiendo conocimiento operativo en documentación y scripts.
