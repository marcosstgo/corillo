// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

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
  integrations: [sitemap({ filter: (u) => !/\/(roadmap|player|embed|bochinchero\/panel)\//.test(u) })],
});
