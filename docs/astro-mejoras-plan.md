# Plan de mejoras Astro — corillo.live

Adopción gradual de funciones avanzadas de Astro sin romper producción.
Estado actual: Astro 6.3.5, 100% estático (`output: 'static'`), sin integraciones,
datos de PocketBase/corillo-api traídos en el cliente, servido de `/dist` por nginx.

**Principio rector:** trabajar en branch, probar el build, deploy = swap de `dist` con
respaldo → rollback trivial. Cada fase es independiente y reversible.

---

## Fase 0 — Red de seguridad · esfuerzo S · riesgo nulo
- Branch `feat/astro-mejoras`, repo limpio.
- Script de deploy: build → respaldar `dist` → swap → restaurar si falla.
- Métricas base (peso de páginas, bytes de imágenes) para medir cada fase.
- No requiere Astro 7.

## Fase 1 — View Transitions + Prefetch · esfuerzo S · riesgo bajo · Astro 6
- `prefetch` en links (preload al hover) — sin riesgo para scripts (navegación normal).
- `<ClientRouter />` en `SiteShell.astro` para navegación SPA — OJO: con tanto script
  inline (player, perfil), probar que todo siga funcionando tras swap; si rompe, dejar
  solo prefetch y posponer ClientRouter con manejo de `astro:page-load`.
- Rollback: quitar líneas del layout/config.

## Fase 2 — Ahorro de banda (imágenes) · esfuerzo M · riesgo bajo · Astro 6
- 2a: `astro:assets` para imágenes estáticas del repo (logos/UI) → AVIF/WebP + responsive + lazy.
- 2b: pipeline de miniaturas dinámicas (avatars/banners PB, thumbs VOD) optimizado en el
  origen (`vod-process.py`/ffmpeg, redimensionado de avatars). Aquí está el grueso del ahorro.

## Fase 3 — Upgrade a Astro 7 (habilitador) · esfuerzo M · riesgo medio
- Prueba de build en copia, arreglar HTML que el compilador Rust (más estricto) rechace.
- Habilita mejores Server Islands/SSR para fases siguientes. Rollback: volver a astro@6.

## Fase 4 — SEO: contenido en el HTML (canal/VOD) · esfuerzo L · riesgo medio-alto
- Hoy el contenido carga por JS → invisible para Google/previews.
- 4a (recomendada): pre-render en build con rebuild periódico (sigue estático).
- 4b: on-demand SSR (adapter Node) solo para esas rutas (datos frescos, más cómputo).
- Primer cambio arquitectónico real.

## Fase 5 — Server Islands para "en vivo ahora" · esfuerzo M · riesgo medio
- Estático + islas server-rendered con caché para lo dinámico (live, viewers, estado).

## Fase 6 (opcional/futuro) — Islas de UI con framework · esfuerzo L
- Migrar lo interactivo pesado (perfil 131KB, player, dashboard) a islas. Refactor, baja prioridad.

---

## Secuencia
Fase 0 → 1 → 2 → 3 → 4 → 5 → [6 opcional]
- Quick wins sin arquitectura: 1 y 2 (sobre Astro 6).
- Cambio arquitectónico: desde Fase 4.
