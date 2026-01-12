import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		host: true,
		proxy: {
			'/api': {
				target: 'https://mv-face-recognition-api.herballemon.workers.dev',
				changeOrigin: true,
				secure: true,
				rewrite: (path) => path
			},
			'/ws': {
				target: 'wss://mv-face-recognition-api.herballemon.workers.dev',
				ws: true,
				changeOrigin: true,
				secure: true
			},
			'/videos': {
				target: 'https://mv-face-recognition-api.herballemon.workers.dev',
				changeOrigin: true,
				secure: true,
				rewrite: (path) => path
			}
		}
	},
	build: {
		target: 'es2022'
	}
});