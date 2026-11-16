import { defineConfig, lazyPlugins } from 'vite-plus';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

/**
 * The Worker that serves `/videos` in development. Deliberately not `VITE_`-prefixed: it is read
 * by the dev server in Node and must never be inlined into the client bundle.
 */
const VIDEOS_ORIGIN = process.env.VIEWER_VIDEOS_ORIGIN ?? 'https://mv.herballemon.dev';

export default defineConfig({
  plugins: lazyPlugins(() => [react(), tailwindcss()]),
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
  server: {
    port: 5180,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Report images live in R2 and are served by the Worker; the local API has no /videos.
      '/videos': {
        target: VIDEOS_ORIGIN,
        changeOrigin: true,
      },
    },
    fs: {
      allow: ['..'],
    },
  },
});
