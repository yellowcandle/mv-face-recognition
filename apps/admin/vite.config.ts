import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'https://mv-face-recognition-api.herballemon.workers.dev',
        changeOrigin: true,
      },
      '/data': {
        target: 'http://localhost:5173',
        rewrite: () => '',
      },
    },
    fs: {
      allow: ['..'],
    },
  },
});
