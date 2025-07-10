<script lang="ts">
	import '../app.css';
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { 
		initializeApp, 
		startHealthChecks, 
		isLoading, 
		error, 
		clearError,
		offlineMode 
	} from '$lib/stores/main';
	
	// Theme management
	let isDarkTheme = false;
	let drawerOpen = false;
	
	// Menu items
	const menuItems = [
		{ title: 'Dashboard', icon: '🏠', href: '/' },
		{ title: 'Video Player', icon: '🎬', href: '/video-player' },
		{ title: 'Video Processing', icon: '🎥', href: '/video-processing' },
		{ title: 'Face Recognition', icon: '👤', href: '/face-recognition' },
		{ title: 'Analytics', icon: '📊', href: '/analytics' },
		{ title: 'Settings', icon: '⚙️', href: '/settings' }
	];
	
	let stopHealthChecks: (() => void) | null = null;
	
	// Toggle theme
	function toggleTheme() {
		isDarkTheme = !isDarkTheme;
		document.documentElement.setAttribute('data-theme', isDarkTheme ? 'dark' : 'light');
	}
	
	// Toggle drawer
	function toggleDrawer() {
		drawerOpen = !drawerOpen;
	}
	
	// Close drawer when clicking outside or on a link
	function closeDrawer() {
		drawerOpen = false;
	}
	
	onMount(async () => {
		// Check for saved theme preference or default to system preference
		const savedTheme = localStorage.getItem('theme');
		if (savedTheme) {
			isDarkTheme = savedTheme === 'dark';
		} else {
			isDarkTheme = window.matchMedia('(prefers-color-scheme: dark)').matches;
		}
		document.documentElement.setAttribute('data-theme', isDarkTheme ? 'dark' : 'light');
		
		// Initialize app
		await initializeApp();
		
		// Start health checks
		stopHealthChecks = startHealthChecks();
	});
	
	onDestroy(() => {
		if (stopHealthChecks) {
			stopHealthChecks();
		}
	});
	
	// Save theme preference
	$: if (typeof localStorage !== 'undefined') {
		localStorage.setItem('theme', isDarkTheme ? 'dark' : 'light');
	}
</script>

<div class="app">
	<!-- Top App Bar -->
	<header class="app-bar">
		<div class="app-bar-content">
			<button class="menu-button" on:click={toggleDrawer} aria-label="Toggle menu">
				☰
			</button>
			
			<div class="app-title">
				<span class="app-icon">🎬</span>
				MV Face Recognition
			</div>
			
			<div class="app-bar-actions">
				{#if $offlineMode}
					<div class="offline-indicator" title="Running in offline mode">
						🔌
					</div>
				{/if}
				<button class="theme-toggle" on:click={toggleTheme} aria-label="Toggle theme">
					{isDarkTheme ? '☀️' : '🌙'}
				</button>
			</div>
		</div>
	</header>

	<!-- Navigation Drawer -->
	{#if drawerOpen}
		<div class="drawer-overlay" on:click={closeDrawer} on:keydown={closeDrawer}></div>
	{/if}
	
	<nav class="drawer" class:open={drawerOpen}>
		<div class="drawer-content">
			<ul class="nav-list">
				{#each menuItems as item}
					<li>
						<a 
							href={item.href} 
							class="nav-item"
							class:active={$page.url.pathname === item.href}
							on:click={closeDrawer}
						>
							<span class="nav-icon">{item.icon}</span>
							<span class="nav-title">{item.title}</span>
						</a>
					</li>
				{/each}
			</ul>
		</div>
	</nav>

	<!-- Main Content -->
	<main class="main-content">
		{#if $isLoading}
			<div class="loading-overlay">
				<div class="loading-spinner"></div>
				<p>Loading...</p>
			</div>
		{/if}
		
		{#if $error}
			<div class="error-banner">
				<div class="error-content">
					<span class="error-icon">⚠️</span>
					<span class="error-message">{$error}</span>
					<button class="error-close" on:click={clearError}>✕</button>
				</div>
			</div>
		{/if}
		
		<div class="content-container">
			<slot />
		</div>
	</main>

	<!-- Footer -->
	<footer class="app-footer">
		<div class="footer-content">
			<span>&copy; 2024 MV Face Recognition System</span>
		</div>
	</footer>
</div>

<style>
	:global([data-theme="dark"]) {
		--primary-color: #2196f3;
		--background-color: #121212;
		--surface-color: #1e1e1e;
		--on-surface-color: #ffffff;
		--text-primary: rgba(255, 255, 255, 0.87);
		--text-secondary: rgba(255, 255, 255, 0.6);
	}

	:global([data-theme="light"]) {
		--primary-color: #1976d2;
		--background-color: #fafafa;
		--surface-color: #ffffff;
		--on-surface-color: #000000;
		--text-primary: rgba(0, 0, 0, 0.87);
		--text-secondary: rgba(0, 0, 0, 0.6);
	}

	.app {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		background-color: var(--background-color);
		color: var(--text-primary);
	}

	.app-bar {
		background-color: var(--primary-color);
		color: white;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
		z-index: 1000;
	}

	.app-bar-content {
		display: flex;
		align-items: center;
		padding: 0 16px;
		height: 64px;
		max-width: 1200px;
		margin: 0 auto;
	}

	.menu-button {
		background: none;
		border: none;
		color: white;
		font-size: 24px;
		cursor: pointer;
		padding: 8px;
		margin-right: 16px;
		border-radius: 4px;
	}

	.menu-button:hover {
		background-color: rgba(255, 255, 255, 0.1);
	}

	.app-title {
		display: flex;
		align-items: center;
		font-size: 20px;
		font-weight: 500;
		flex: 1;
	}

	.app-icon {
		margin-right: 8px;
		font-size: 24px;
	}

	.app-bar-actions {
		display: flex;
		align-items: center;
	}

	.theme-toggle {
		background: none;
		border: none;
		color: white;
		font-size: 24px;
		cursor: pointer;
		padding: 8px;
		border-radius: 4px;
	}

	.theme-toggle:hover {
		background-color: rgba(255, 255, 255, 0.1);
	}

	.offline-indicator {
		color: #ffaa00;
		font-size: 20px;
		margin-right: 8px;
		padding: 4px;
		border-radius: 4px;
		background-color: rgba(255, 255, 255, 0.1);
	}

	.drawer-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(0, 0, 0, 0.5);
		z-index: 999;
	}

	.drawer {
		position: fixed;
		top: 64px;
		left: -280px;
		width: 280px;
		height: calc(100vh - 64px);
		background-color: var(--surface-color);
		box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
		transition: left 0.3s ease;
		z-index: 1000;
		overflow-y: auto;
	}

	.drawer.open {
		left: 0;
	}

	.drawer-content {
		padding: 16px 0;
	}

	.nav-list {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.nav-item {
		display: flex;
		align-items: center;
		padding: 12px 24px;
		text-decoration: none;
		color: var(--text-primary);
		transition: background-color 0.2s ease;
	}

	.nav-item:hover {
		background-color: rgba(var(--primary-color), 0.1);
	}

	.nav-item.active {
		background-color: rgba(var(--primary-color), 0.2);
		color: var(--primary-color);
	}

	.nav-icon {
		margin-right: 16px;
		font-size: 20px;
	}

	.nav-title {
		font-size: 16px;
	}

	.main-content {
		flex: 1;
		position: relative;
		padding-top: 64px; /* Account for fixed app bar */
	}

	.loading-overlay {
		position: fixed;
		top: 64px;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(var(--background-color), 0.8);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		z-index: 999;
	}

	.loading-spinner {
		width: 40px;
		height: 40px;
		border: 4px solid rgba(var(--primary-color), 0.3);
		border-top: 4px solid var(--primary-color);
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin-bottom: 16px;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	.error-banner {
		background-color: var(--error-color);
		color: white;
		padding: 16px;
		margin: 16px;
		border-radius: 4px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.error-content {
		display: flex;
		align-items: center;
		max-width: 1200px;
		margin: 0 auto;
	}

	.error-icon {
		margin-right: 12px;
		font-size: 20px;
	}

	.error-message {
		flex: 1;
	}

	.error-close {
		background: none;
		border: none;
		color: white;
		font-size: 20px;
		cursor: pointer;
		padding: 4px;
		border-radius: 4px;
	}

	.error-close:hover {
		background-color: rgba(255, 255, 255, 0.1);
	}

	.content-container {
		max-width: 1200px;
		margin: 0 auto;
		padding: 24px;
	}

	.app-footer {
		background-color: var(--surface-color);
		border-top: 1px solid rgba(var(--text-primary), 0.1);
		padding: 16px;
		text-align: center;
	}

	.footer-content {
		max-width: 1200px;
		margin: 0 auto;
		color: var(--text-secondary);
	}

	@media (max-width: 768px) {
		.app-bar-content {
			padding: 0 12px;
		}

		.content-container {
			padding: 16px;
		}

		.drawer {
			width: 100%;
			left: -100%;
		}
	}
</style>