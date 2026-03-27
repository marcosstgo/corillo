import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/react-demo/',
  build: { outDir: '../react-demo-dist', emptyOutDir: true },
});
