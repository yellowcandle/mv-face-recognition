Coding conventions for mv-face-recognition

Python:
- Python 3.9+ with type hints
- Docstrings for public functions/classes (PEP257)
- Use ruff for linting and formatting where applicable
- Avoid one-letter variable names; prefer descriptive names
- Prefer generators/streams for large data processing (do not load all frames into memory)
- Use logging with structured messages (logger.info/debug/warning/error)
- Tests with pytest; prefer small unit tests and integration tests for pipeline
- Use dataclasses for simple data containers

JavaScript/TypeScript (frontend & worker):
- TypeScript types and interfaces in `frontend/src/lib/types`
- SvelteKit conventions: routes in `src/routes`, pages use `+page.svelte` and `+page.ts`
- ESLint and Prettier for formatting
- Use `stores` for shared state in Svelte, small components in `components/`

General:
- Document changes in `DESIGN.md` for major design updates
- Add implementation notes to corresponding backlog task
- Avoid modifying critical files unless necessary (README.md, metadata/contestant_info.csv)
- Keep commits small and focused

Testing & CI:
- Run local tests before pushing
- Maintain coverage thresholds as defined in CLAUDE.md

