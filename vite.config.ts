import { defineConfig } from "vite-plus";

// The repo carries a lot of pre-Vite+ history (generated reports, retired scripts,
// vendored worker assets). Keep the unified check focused on code that still ships;
// widen these as the legacy trees are removed.
const legacy = [
  "dist/**",
  "node_modules/**",
  "local_output/**",
  "source/**",
  "metadata/**",
  "data/**",
  "docs/**",
  "scripts/**",
  "mvp-processor/**",
  "worker/public/**",
  "worker/embedded-assets.js",
  "safety_*.json",
  "security_*.json",
  "final_safety_scan_report.json",
];

export default defineConfig({
  fmt: {
    ignorePatterns: legacy,
  },
  lint: {
    ignorePatterns: legacy,
    jsPlugins: [{ name: "vite-plus", specifier: "vite-plus/oxlint-plugin" }],
    rules: { "vite-plus/prefer-vite-plus-imports": "error" },
    options: { typeAware: true, typeCheck: true },
  },
  test: {
    // Agent worktrees carry whole copies of the repo, tests included.
    exclude: [".claude/**", "node_modules/**", "dist/**"],
  },
});
