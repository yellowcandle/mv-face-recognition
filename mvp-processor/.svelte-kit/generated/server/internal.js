
import root from '../root.js';
import { set_building, set_prerendering } from '__sveltekit/environment';
import { set_assets } from '__sveltekit/paths';
import { set_manifest, set_read_implementation } from '__sveltekit/server';
import { set_private_env, set_public_env } from '../../../node_modules/@sveltejs/kit/src/runtime/shared-server.js';

export const options = {
	app_template_contains_nonce: false,
	csp: {"mode":"auto","directives":{"upgrade-insecure-requests":false,"block-all-mixed-content":false},"reportOnly":{"upgrade-insecure-requests":false,"block-all-mixed-content":false}},
	csrf_check_origin: true,
	csrf_trusted_origins: [],
	embedded: false,
	env_public_prefix: 'PUBLIC_',
	env_private_prefix: '',
	hash_routing: false,
	hooks: null, // added lazily, via `get_hooks`
	preload_strategy: "modulepreload",
	root,
	service_worker: false,
	service_worker_options: undefined,
	templates: {
		app: ({ head, body, assets, nonce, env }) => "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"utf-8\" />\n    <meta name=\"description\" content=\"MV Face Recognition - AI-powered video face detection and recognition system\" />\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n    <title>Face Recognition Dashboard</title>\n    <link rel=\"icon\" href=\"" + assets + "/favicon.png\" />\n    " + head + "\n    <style>\n        :root {\n            /* Color Palette */\n            --primary-color: #2563eb;\n            --primary-hover: #1d4ed8;\n            --secondary-color: #64748b;\n            --success-color: #22c55e;\n            --warning-color: #eab308;\n            --error-color: #ef4444;\n            --info-color: #3b82f6;\n\n            /* Surface Colors */\n            --bg-color: #ffffff;\n            --surface-color: #f8fafc;\n            --border-color: #e2e8f0;\n            --text-color: #1e293b;\n            --text-secondary: #64748b;\n            --text-muted: #94a3b8;\n\n            /* Dark mode */\n            --dark-bg-color: #0f172a;\n            --dark-surface-color: #1e293b;\n            --dark-border-color: #334155;\n            --dark-text-color: #f1f5f9;\n            --dark-text-secondary: #94a3b8;\n\n            /* Shadows */\n            --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);\n            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);\n\n            /* Transitions */\n            --transition: all 0.2s ease;\n        }\n\n        [data-theme=\"dark\"] {\n            --bg-color: var(--dark-bg-color);\n            --surface-color: var(--dark-surface-color);\n            --border-color: var(--dark-border-color);\n            --text-color: var(--dark-text-color);\n            --text-secondary: var(--dark-text-secondary);\n        }\n\n        * {\n            box-sizing: border-box;\n            margin: 0;\n            padding: 0;\n        }\n\n        body {\n            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;\n            background-color: var(--bg-color);\n            color: var(--text-color);\n            line-height: 1.6;\n            transition: var(--transition);\n        }\n\n        /* Face Recognition Dashboard Specific Styles */\n        .dashboard-layout {\n            min-height: 100vh;\n            background-color: #1a1a1a;\n            color: #ffffff;\n            display: flex;\n            flex-direction: column;\n        }\n\n        .header-bar {\n            height: 60px;\n            background-color: #2a2a2a;\n            display: flex;\n            align-items: center;\n            justify-content: space-between;\n            padding: 0 20px;\n            border-bottom: 1px solid #444;\n        }\n\n        .app-title {\n            font-size: 20px;\n            font-weight: 600;\n            color: #ffffff;\n        }\n\n        .status-indicator {\n            background-color: #22c55e;\n            color: #000;\n            padding: 6px 12px;\n            border-radius: 4px;\n            font-weight: 600;\n            font-size: 12px;\n            animation: pulse 2s infinite;\n        }\n\n        @keyframes pulse {\n            0%, 100% { opacity: 1; }\n            50% { opacity: 0.7; }\n        }\n\n        .main-content {\n            flex: 1;\n            display: flex;\n            min-height: calc(100vh - 260px);\n        }\n\n        .video-panel {\n            width: 60%;\n            background-color: #000000;\n            position: relative;\n            border-right: 1px solid #444;\n        }\n\n        .face-panel {\n            width: 40%;\n            background-color: #1e293b;\n            padding: 20px;\n            overflow-y: auto;\n        }\n\n        .similarity-panel {\n            height: 200px;\n            background-color: #374151;\n            padding: 20px;\n            border-top: 1px solid #444;\n        }\n    </style>\n</head>\n<body data-sveltekit-preload-data=\"hover\">\n    <div style=\"display: contents\">" + body + "</div>\n</body>\n</html>",
		error: ({ status, message }) => "<!doctype html>\n<html lang=\"en\">\n\t<head>\n\t\t<meta charset=\"utf-8\" />\n\t\t<title>" + message + "</title>\n\n\t\t<style>\n\t\t\tbody {\n\t\t\t\t--bg: white;\n\t\t\t\t--fg: #222;\n\t\t\t\t--divider: #ccc;\n\t\t\t\tbackground: var(--bg);\n\t\t\t\tcolor: var(--fg);\n\t\t\t\tfont-family:\n\t\t\t\t\tsystem-ui,\n\t\t\t\t\t-apple-system,\n\t\t\t\t\tBlinkMacSystemFont,\n\t\t\t\t\t'Segoe UI',\n\t\t\t\t\tRoboto,\n\t\t\t\t\tOxygen,\n\t\t\t\t\tUbuntu,\n\t\t\t\t\tCantarell,\n\t\t\t\t\t'Open Sans',\n\t\t\t\t\t'Helvetica Neue',\n\t\t\t\t\tsans-serif;\n\t\t\t\tdisplay: flex;\n\t\t\t\talign-items: center;\n\t\t\t\tjustify-content: center;\n\t\t\t\theight: 100vh;\n\t\t\t\tmargin: 0;\n\t\t\t}\n\n\t\t\t.error {\n\t\t\t\tdisplay: flex;\n\t\t\t\talign-items: center;\n\t\t\t\tmax-width: 32rem;\n\t\t\t\tmargin: 0 1rem;\n\t\t\t}\n\n\t\t\t.status {\n\t\t\t\tfont-weight: 200;\n\t\t\t\tfont-size: 3rem;\n\t\t\t\tline-height: 1;\n\t\t\t\tposition: relative;\n\t\t\t\ttop: -0.05rem;\n\t\t\t}\n\n\t\t\t.message {\n\t\t\t\tborder-left: 1px solid var(--divider);\n\t\t\t\tpadding: 0 0 0 1rem;\n\t\t\t\tmargin: 0 0 0 1rem;\n\t\t\t\tmin-height: 2.5rem;\n\t\t\t\tdisplay: flex;\n\t\t\t\talign-items: center;\n\t\t\t}\n\n\t\t\t.message h1 {\n\t\t\t\tfont-weight: 400;\n\t\t\t\tfont-size: 1em;\n\t\t\t\tmargin: 0;\n\t\t\t}\n\n\t\t\t@media (prefers-color-scheme: dark) {\n\t\t\t\tbody {\n\t\t\t\t\t--bg: #222;\n\t\t\t\t\t--fg: #ddd;\n\t\t\t\t\t--divider: #666;\n\t\t\t\t}\n\t\t\t}\n\t\t</style>\n\t</head>\n\t<body>\n\t\t<div class=\"error\">\n\t\t\t<span class=\"status\">" + status + "</span>\n\t\t\t<div class=\"message\">\n\t\t\t\t<h1>" + message + "</h1>\n\t\t\t</div>\n\t\t</div>\n\t</body>\n</html>\n"
	},
	version_hash: "17g057g"
};

export async function get_hooks() {
	let handle;
	let handleFetch;
	let handleError;
	let handleValidationError;
	let init;
	

	let reroute;
	let transport;
	

	return {
		handle,
		handleFetch,
		handleError,
		handleValidationError,
		init,
		reroute,
		transport
	};
}

export { set_assets, set_building, set_manifest, set_prerendering, set_private_env, set_public_env, set_read_implementation };
