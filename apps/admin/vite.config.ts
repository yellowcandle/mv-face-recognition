import { defineConfig, lazyPlugins } from 'vite-plus';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  // Served by the Worker from /admin — absolute asset URLs must carry the prefix.
  base: '/admin/',
  plugins: lazyPlugins(() => [react(), tailwindcss()]),
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    // ponytail: exact tailnet host only, served by `tailscale serve` (not funnel)
    allowedHosts: ['yellowcandle-macbook-air-2-1.tail1fa667.ts.net'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
    fs: {
      allow: ['..'],
    },
  },
});
