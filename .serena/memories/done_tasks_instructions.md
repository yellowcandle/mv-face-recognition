When a task is completed, follow these steps:

1. Run tests relevant to your change:
   - Python: `cd mvp-processor && pytest tests/ -q`
   - Frontend: `cd frontend && npm run test:coverage`
2. Run linters and formatters:
   - `cd mvp-processor && ruff check . && ruff format .`
   - `cd frontend && npm run lint && npm run format`
3. Update `DESIGN.md` with Implementation Notes summarizing approach and files modified
4. Update backlog task file under `backlog/tasks/` and mark acceptance criteria as completed
5. Push branch and open PR; include short summary and reference backlog task

DoD checklist to mark done:
- [ ] Relevant tests pass
- [ ] Linter & formatter pass
- [ ] Implementation notes added to `DESIGN.md`
- [ ] Backlog task acceptance criteria checked off
- [ ] PR created with clear description

