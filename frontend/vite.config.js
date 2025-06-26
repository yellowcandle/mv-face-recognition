import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true
      }
    }
  },
  build: {
    target: 'esnext',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['svelte'],
          video: ['video.js'],
          audio: ['wavesurfer.js'],
          graphics: ['three'],
          data: ['@msgpack/msgpack', 'chart.js']
        }
      }
    }
  },
  optimizeDeps: {
    include: ['video.js', 'wavesurfer.js', 'three', '@msgpack/msgpack']
  }
})