// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { readdirSync } from 'node:fs';

// Cine: al sitemap solo las fichas con texto propio de Corillo (src/content/cine/*.md). Las que solo tienen datos de
// TMDB llevan noindex (texto repetido en miles de sitios) y no se listan (1-nov-2026).
const FICHAS_PROPIAS = new Set(readdirSync(new URL('./src/content/cine/', import.meta.url)).filter(f => f.endsWith('.md')).map(f => f.slice(0, -3)));
const fichaAjena = (u) => { const m = u.match(/\/cine\/([^/]+)\/$/); return !!m && m[1] !== 'pr' && !FICHAS_PROPIAS.has(m[1]); };

export default defineConfig({
  site: 'https://corillo.live',
  output: 'static',
  outDir: 'dist',
  build: {
    format: 'directory',
  },
  trailingSlash: 'always',
  prefetch: {
    prefetchAll: true,
    defaultStrategy: 'hover',
  },
  // Fuera del sitemap: páginas sin contenido propio o con noindex (31-oct-2026).
  integrations: [sitemap({ filter: (u) => !/\/(roadmap|player|embed|bochinchero\/panel)\//.test(u) && !fichaAjena(u) })],
});
