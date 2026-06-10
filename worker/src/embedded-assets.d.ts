declare module '../embedded-assets.js' {
  export const EMBEDDED_ASSETS: Record<string, string>;
  export const BINARY_ASSETS: Set<string>;
}

declare module '../embedded-assets' {
  export const EMBEDDED_ASSETS: Record<string, string>;
  export const BINARY_ASSETS: Set<string>;
}
