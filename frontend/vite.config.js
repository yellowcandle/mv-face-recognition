import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(process.cwd(), './src'),
      '@/modules': path.resolve(process.cwd(), './src/modules'),
      '@/core': path.resolve(process.cwd(), './src/core')
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@import "vuetify/settings";`,
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          ui: ['vuetify'],
          utils: ['axios', 'socket.io-client']
        }
      }
    }
  }
})