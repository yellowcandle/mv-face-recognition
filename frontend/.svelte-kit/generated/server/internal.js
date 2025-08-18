
import root from '../root.js';
import { set_building, set_prerendering } from '__sveltekit/environment';
import { set_assets } from '__sveltekit/paths';
import { set_manifest, set_read_implementation } from '__sveltekit/server';
import { set_private_env, set_public_env, set_safe_public_env } from '../../../node_modules/@sveltejs/kit/src/runtime/shared-server.js';

export const options = {
	app_template_contains_nonce: false,
	csp: {"mode":"auto","directives":{"upgrade-insecure-requests":false,"block-all-mixed-content":false},"reportOnly":{"upgrade-insecure-requests":false,"block-all-mixed-content":false}},
	csrf_check_origin: true,
	embedded: false,
	env_public_prefix: 'PUBLIC_',
	env_private_prefix: '',
	hash_routing: false,
	hooks: null, // added lazily, via `get_hooks`
	preload_strategy: "modulepreload",
	root,
	service_worker: false,
	templates: {
		app: ({ head, body, assets, nonce, env }) => "<!DOCTYPE html>\n<html lang=\"en\" %sveltekit.theme%>\n  <head>\n    <meta charset=\"utf-8\" />\n    <link rel=\"icon\" href=\"" + assets + "/favicon.png\" />\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n    <meta name=\"description\" content=\"MV Face Recognition - Advanced video processing with real-time face detection and recognition\" />\n    <meta name=\"keywords\" content=\"face recognition, video processing, AI, machine learning, contestant identification\" />\n    \n    <!-- Open Graph Meta Tags -->\n    <meta property=\"og:title\" content=\"MV Face Recognition\" />\n    <meta property=\"og:description\" content=\"Advanced video processing with real-time face detection and recognition\" />\n    <meta property=\"og:type\" content=\"website\" />\n    \n    <!-- CSS Variables for Theming -->\n    <style>\n      :root {\n        --primary-color: #2563eb;\n        --primary-hover: #1d4ed8;\n        --primary-light: #dbeafe;\n        --secondary-color: #64748b;\n        --success-color: #10b981;\n        --success-light: #d1fae5;\n        --warning-color: #f59e0b;\n        --warning-light: #fef3c7;\n        --error-color: #ef4444;\n        --error-light: #fecaca;\n        --background-color: #ffffff;\n        --surface-color: #f8fafc;\n        --surface-elevated: #ffffff;\n        --text-color: #1e293b;\n        --text-secondary: #64748b;\n        --text-muted: #94a3b8;\n        --border-color: #e2e8f0;\n        --border-hover: #cbd5e1;\n        --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);\n        --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);\n        --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);\n        --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);\n        --radius-sm: 0.375rem;\n        --radius: 0.5rem;\n        --radius-md: 0.75rem;\n        --radius-lg: 1rem;\n      }\n      \n      @media (prefers-color-scheme: dark) {\n        :root {\n          --background-color: #0f172a;\n          --surface-color: #1e293b;\n          --surface-elevated: #334155;\n          --text-color: #f1f5f9;\n          --text-secondary: #94a3b8;\n          --text-muted: #64748b;\n          --border-color: #334155;\n          --border-hover: #475569;\n          --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.2);\n          --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.3), 0 1px 2px -1px rgb(0 0 0 / 0.3);\n          --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.3), 0 2px 4px -2px rgb(0 0 0 / 0.3);\n          --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.3), 0 4px 6px -4px rgb(0 0 0 / 0.3);\n        }\n      }\n      \n      * {\n        box-sizing: border-box;\n      }\n      \n      body {\n        margin: 0;\n        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;\n        background-color: var(--background-color);\n        color: var(--text-color);\n        line-height: 1.6;\n        transition: background-color 0.3s ease, color 0.3s ease;\n      }\n      \n      .loading {\n        display: flex;\n        justify-content: center;\n        align-items: center;\n        height: 100vh;\n        font-size: 1.1rem;\n        color: var(--text-secondary);\n      }\n      \n      .loading::after {\n        content: '';\n        width: 20px;\n        height: 20px;\n        border: 2px solid var(--border-color);\n        border-top: 2px solid var(--primary-color);\n        border-radius: 50%;\n        animation: spin 1s linear infinite;\n        margin-left: 10px;\n      }\n      \n      @keyframes spin {\n        0% { transform: rotate(0deg); }\n        100% { transform: rotate(360deg); }\n      }\n    </style>\n    \n    " + head + "\n  </head>\n  <body data-sveltekit-preload-data=\"hover\">\n    <div style=\"display: contents\">\n      <div style=\"display: contents\" class=\"loading\">Loading MV Face Recognition...</div>\n      " + body + "\n    </div>\n  </body>\n</html>",
		error: ({ status, message }) => "<!doctype html>\n<html lang=\"en\">\n\t<head>\n\t\t<meta charset=\"utf-8\" />\n\t\t<title>" + message + "</title>\n\n\t\t<style>\n\t\t\tbody {\n\t\t\t\t--bg: white;\n\t\t\t\t--fg: #222;\n\t\t\t\t--divider: #ccc;\n\t\t\t\tbackground: var(--bg);\n\t\t\t\tcolor: var(--fg);\n\t\t\t\tfont-family:\n\t\t\t\t\tsystem-ui,\n\t\t\t\t\t-apple-system,\n\t\t\t\t\tBlinkMacSystemFont,\n\t\t\t\t\t'Segoe UI',\n\t\t\t\t\tRoboto,\n\t\t\t\t\tOxygen,\n\t\t\t\t\tUbuntu,\n\t\t\t\t\tCantarell,\n\t\t\t\t\t'Open Sans',\n\t\t\t\t\t'Helvetica Neue',\n\t\t\t\t\tsans-serif;\n\t\t\t\tdisplay: flex;\n\t\t\t\talign-items: center;\n\t\t\t\tjustify-content: center;\n\t\t\t\theight: 100vh;\n\t\t\t\tmargin: 0;\n\t\t\t}\n\n\t\t\t.error {\n\t\t\t\tdisplay: flex;\n\t\t\t\talign-items: center;\n\t\t\t\tmax-width: 32rem;\n\t\t\t\tmargin: 0 1rem;\n\t\t\t}\n\n\t\t\t.status {\n\t\t\t\tfont-weight: 200;\n\t\t\t\tfont-size: 3rem;\n\t\t\t\tline-height: 1;\n\t\t\t\tposition: relative;\n\t\t\t\ttop: -0.05rem;\n\t\t\t}\n\n\t\t\t.message {\n\t\t\t\tborder-left: 1px solid var(--divider);\n\t\t\t\tpadding: 0 0 0 1rem;\n\t\t\t\tmargin: 0 0 0 1rem;\n\t\t\t\tmin-height: 2.5rem;\n\t\t\t\tdisplay: flex;\n\t\t\t\talign-items: center;\n\t\t\t}\n\n\t\t\t.message h1 {\n\t\t\t\tfont-weight: 400;\n\t\t\t\tfont-size: 1em;\n\t\t\t\tmargin: 0;\n\t\t\t}\n\n\t\t\t@media (prefers-color-scheme: dark) {\n\t\t\t\tbody {\n\t\t\t\t\t--bg: #222;\n\t\t\t\t\t--fg: #ddd;\n\t\t\t\t\t--divider: #666;\n\t\t\t\t}\n\t\t\t}\n\t\t</style>\n\t</head>\n\t<body>\n\t\t<div class=\"error\">\n\t\t\t<span class=\"status\">" + status + "</span>\n\t\t\t<div class=\"message\">\n\t\t\t\t<h1>" + message + "</h1>\n\t\t\t</div>\n\t\t</div>\n\t</body>\n</html>\n"
	},
	version_hash: "o2jf5g"
};

export async function get_hooks() {
	let handle;
	let handleFetch;
	let handleError;
	let init;
	

	let reroute;
	let transport;
	

	return {
		handle,
		handleFetch,
		handleError,
		init,
		reroute,
		transport
	};
}

export { set_assets, set_building, set_manifest, set_prerendering, set_private_env, set_public_env, set_read_implementation, set_safe_public_env };
