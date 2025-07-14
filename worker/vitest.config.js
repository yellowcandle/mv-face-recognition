import { defineConfig } from 'vitest/config';

export default defineConfig({
	test: {
		environment: 'miniflare',
		environmentOptions: {
			bindings: {
				TEST_MODE: 'true'
			},
			kvNamespaces: ['METADATA_KV'],
			r2Buckets: ['VIDEOS_BUCKET']
		},
		coverage: {
			provider: 'v8',
			reporter: ['text', 'json', 'html'],
			include: ['*.js'],
			exclude: ['tests/**/*', 'node_modules/**/*'],
			thresholds: {
				statements: 90,
				branches: 85,
				functions: 90,
				lines: 90
			}
		}
	}
});