// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  outDir: 'dist',
  build: {
    format: 'directory',
  },
  trailingSlash: 'always',
});
