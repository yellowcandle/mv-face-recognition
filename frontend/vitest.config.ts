import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
	plugins: [sveltekit()],
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}'],
		exclude: ['src/**/*.e2e.{test,spec}.{js,ts}'],
		environment: 'jsdom',
		globals: true,
		setupFiles: ['src/tests/setup.ts'],
		coverage: {
			provider: 'v8',
			reporter: ['text', 'json', 'html'],
			include: ['src/**/*.{js,ts,svelte}'],
			exclude: [
				'src/**/*.test.{js,ts}',
				'src/**/*.spec.{js,ts}',
				'src/tests/**/*',
				'src/app.html'
			],
			thresholds: {
				statements: 80,
				branches: 75,
				functions: 85,
				lines: 80
			}
		}
	}
});