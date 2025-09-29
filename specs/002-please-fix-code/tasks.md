# Tasks: code improvement

**Input**: Design documents from `/specs/002-please-fix-code/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/, quickstart.md

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Web app**: `backend/src/`, `frontend/src/`
- Paths shown below assume web app structure - adjust based on plan.md

## Phase 3.1: Setup
- [X] T001 Install security tools (bandit, safety) and configure Python environment
- [X] T002 Configure ESLint security plugin for frontend in frontend/package.json
- [X] T003 Configure security linting for backend Python project

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [X] T004 [P] Contract test for input validation in tests/contract/test_input_validation.py
- [X] T005 [P] Contract test for data protection in tests/contract/test_data_protection.py
- [X] T006 [P] Contract test for access control in tests/contract/test_access_control.py
- [X] T007 [P] Contract test for error handling in tests/contract/test_error_handling.py
- [X] T008 [P] Contract test for compliance in tests/contract/test_compliance.py
- [X] T009 [P] Integration test for security bug fixes in tests/integration/test_security_fixes.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [X] T010 [P] Implement input validation in backend/src/validation.py
- [X] T011 [P] Implement data encryption in backend/src/encryption.py
- [X] T012 [P] Implement access control middleware in backend/src/middleware/auth.py
- [X] T013 [P] Implement secure error handling in backend/src/error_handlers.py
- [X] T014 [P] Implement compliance checks in backend/src/compliance.py

## Phase 3.4: Integration
- [X] T015 Connect encryption to data models in backend/src/models/
- [X] T016 Integrate access control with API routes in backend/src/api/
- [X] T017 Add secure logging in backend/src/logging.py
- [X] T018 Configure security headers in backend/src/middleware/security.py

## Phase 3.5: Polish
- [X] T019 [P] Unit tests for security functions in tests/unit/test_security.py
- [X] T020 Security performance tests (<200ms response times)
- [X] T021 [P] Update security documentation in docs/security.md
- [X] T022 Run quickstart validation checklist

## Dependencies
- Tests (T004-T009) before implementation (T010-T014)
- T010 blocks T015
- T012 blocks T016
- Implementation before polish (T019-T022)

## Parallel Example
```
# Launch T004-T009 together:
Task: "Contract test for input validation in tests/contract/test_input_validation.py"
Task: "Contract test for data protection in tests/contract/test_data_protection.py"
Task: "Contract test for access control in tests/contract/test_access_control.py"
Task: "Contract test for error handling in tests/contract/test_error_handling.py"
Task: "Contract test for compliance in tests/contract/test_compliance.py"
Task: "Integration test for security bug fixes in tests/integration/test_security_fixes.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Avoid: vague tasks, same file conflicts

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   - Each contract file → contract test task [P]
   - Each endpoint → implementation task
   
2. **From Data Model**:
   - Each entity → model creation task [P]
   - Relationships → service layer tasks
   
3. **From User Stories**:
   - Each story → integration test [P]
   - Quickstart scenarios → validation tasks

4. **Ordering**:
   - Setup → Tests → Models → Services → Endpoints → Polish
   - Dependencies block parallel execution

## Validation Checklist
*GATE: Checked by main() before returning*

- [ ] All contracts have corresponding tests
- [ ] All entities have model tasks
- [ ] All tests come before implementation
- [ ] Parallel tasks truly independent
- [ ] Each task specifies exact file path
- [ ] No task modifies same file as another [P] task