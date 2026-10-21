---
status: accepted
---

# The viewer and admin keep declarative React Router

The **viewer** and **admin** stay on React Router 8 in declarative mode. We do not adopt
TanStack Router, TanStack Start, Next.js, Astro or SvelteKit now.

## Context

Both apps are single-page applications. The **viewer** is read-only and ships as static files
inside the Cloudflare Worker. The **admin** is local-only and talks to `local_api.py` on
localhost. All data arrives over `fetch` from the Worker or the local API.

There is no server rendering, no server function and no route loader today. The URL state is
one query parameter, `?video=`, on the player. The remaining state (sort order, filters,
selection) is component state.

The current stack is React Router **8.5.0** in declarative mode: `<BrowserRouter>` and
`<Routes>`, with seven routed paths in the admin and four in the viewer. The v8 upgrade removed
the `react-router-dom` package and changed nothing in the source, because every import already
came from `react-router`.

We evaluated these options against the same requirements: static hosting, no server, one
client-side parameter, and a small route count.

## Considered options

- **TanStack Router.** Rejected *for now*. Its strongest feature is type-safe path and search
  parameters, with schema validation and loaders. The viewer has one search parameter. Migration
  would touch eight routes, every `Link` and the shared `Player`; the benefit arrives only when
  URL state becomes complex. It remains the first option if that changes.
- **TanStack Start.** Rejected. Start 1.0 is stable (October 2026) and has an SPA mode, but that
  mode adds a prerender step and a `_shell.html` with rewrite rules. The Worker already serves an
  embedded `index.html`; the shell adds a second serving convention for no feature we use.
  Start's value is server rendering and typed server functions, and this project has neither.
- **Next.js.** Rejected. Its model is React Server Components and server rendering. The product
  is a static, read-only viewer and a local admin. Next also brings a second build system next
  to the Vite toolchain we already run.
- **Astro and SvelteKit.** Rejected. Astro is for content pages with islands, not a stateful
  player and back office. SvelteKit would replace React, which this repo deliberately settled
  on.
- **React Router 8 declarative (chosen).** It is already deployed, the v8 baseline is met
  (Node 22.22, React 19.2.7, Vite 7), and the router is a leaf dependency: the build, test and
  deploy paths do not depend on which router the apps use.

## Consequences

- **React Router's framework mode is not used.** If the viewer ever needs server rendering or
  route loaders, that is a new ADR: it adds a server runtime and changes how the Worker serves
  the app, which ADR 0003 currently keeps static and read-only.
- **Vite+ and the router stay independent.** Replacing either one does not require replacing
  the other. Vite+ owns `dev`, `build`, `check` and `test`; React Router owns the URL.
- **Upgrade within major 8.** React Router now ships yearly majors; v6 and Remix v2 are end of
  life. Stay on 8.x, and treat a v9 baseline bump as a normal dependency change, not a
  migration project.
- **Revisit triggers.** Adopt TanStack Router if URL state grows beyond a single parameter
  (saved filters, shareable analytics views, deep-linked labelling state). Adopt a full-stack
  framework only if a server-side feature cannot be served by the Worker and the local API.
- **No new dependency was added for this decision.** Phase 4 changes documentation only.
