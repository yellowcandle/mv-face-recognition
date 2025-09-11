# Tasks: Face Recognition System for Contestant Detection

**Input**: Design documents from `/specs/001-this-is-a/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/, quickstart.md

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → Extract: tech stack (Python 3.11+, InsightFace, Supervision, OpenCV, ChromaDB, FFmpeg-python), structure (src/core, src/services, src/cli, tests/)
2. Load optional design documents:
   → data-model.md: Entities (Contestant, FaceEmbedding, DetectedFace, BoundingBox, AnnotatedFrame, AnnotatedVideo, ProcessingStats) → model tasks
   → contracts/: cli_interface.md, processing_api.md, supervision_integration.md → contract test tasks
   → research.md: Decisions (InsightFace pipeline, frame-by-frame processing, ChromaDB storage) → setup tasks
   → quickstart.md: Scenarios (init, process, status, review results) → integration tests
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB connections, middleware, logging
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
- **Single project**: `src/`, `tests/` at repository root
- Paths based on plan.md structure: src/core/, src/services/, src/cli/, tests/contract/, tests/integration/, tests/unit/

## Phase 3.1: Setup
- [ ] T001 Create project structure per implementation plan in src/ (core/, services/, cli/, models/)
- [ ] T002 Initialize Python project with dependencies (InsightFace, Supervision, OpenCV, ChromaDB, FFmpeg-python) in pyproject.toml
- [ ] T003 [P] Configure linting and formatting tools (black, isort, flake8, mypy) in pyproject.toml

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T004 [P] Contract test CLI interface in tests/contract/test_cli_interface.py (from contracts/cli_interface.md)
- [ ] T005 [P] Contract test processing API in tests/contract/test_processing_api.py (from contracts/processing_api.md)
- [ ] T006 [P] Contract test supervision integration in tests/contract/test_supervision_integration.py (from contracts/supervision_integration.md)
- [ ] T007 [P] Integration test system initialization in tests/integration/test_init.py (from quickstart.md Step 1)
- [ ] T008 [P] Integration test video processing workflow in tests/integration/test_process.py (from quickstart.md Step 2)
- [ ] T009 [P] Integration test status and results review in tests/integration/test_status_review.py (from quickstart.md Steps 3-4)
- [ ] T010 [P] Integration test edge cases (no contestants, poor quality, many faces) in tests/integration/test_edge_cases.py (from quickstart.md Step 5)

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [ ] T011 [P] Contestant model in src/models/contestant.py (from data-model.md)
- [ ] T012 [P] FaceEmbedding model in src/models/embedding.py (from data-model.md)
- [ ] T013 [P] DetectedFace model in src/models/detection.py (from data-model.md)
- [ ] T014 [P] BoundingBox model in src/models/bbox.py (from data-model.md)
- [ ] T015 [P] AnnotatedFrame model in src/models/annotated_frame.py (from data-model.md)
- [ ] T016 [P] AnnotatedVideo model in src/models/annotated_video.py (from data-model.md)
- [ ] T017 [P] ProcessingStats model in src/models/processing_stats.py (from data-model.md)
- [ ] T018 FaceDetector service in src/core/face_detector.py (from research.md)
- [ ] T019 FaceMatcher service in src/core/face_matcher.py (from research.md)
- [ ] T020 VideoProcessor service in src/services/video_processor.py (from research.md)
- [ ] T021 EmbeddingManager service in src/services/embedding_manager.py (from research.md)
- [ ] T022 CLI commands (init, process, list, status) in src/cli/main.py (from contracts/cli_interface.md and quickstart.md)

## Phase 3.4: Integration
- [ ] T023 Connect EmbeddingManager to ChromaDB in src/services/embedding_manager.py
- [ ] T024 Integrate FaceDetector with Supervision in src/core/face_detector.py
- [ ] T025 Video frame tracking integration in src/core/face_tracker.py
- [ ] T026 FFmpeg integration for video reconstruction in src/services/video_processor.py
- [ ] T027 GPU acceleration setup (CUDA/CoreML) in src/core/face_detector.py and src/core/face_matcher.py
- [ ] T028 Input validation and error handling across services
- [ ] T029 Structured logging implementation in all services

## Phase 3.5: Polish
- [ ] T030 [P] Unit tests for models in tests/unit/test_models.py
- [ ] T031 [P] Unit tests for services in tests/unit/test_services.py
- [ ] T032 Performance tests (processing speed <2s/frame, memory <2GB) in tests/unit/test_performance.py
- [ ] T033 [P] Update docs with API and CLI documentation in docs/
- [ ] T034 Refactor for code duplication removal across core services
- [ ] T035 Run quickstart.md validation scenarios manually

## Dependencies
- Setup (T001-T003) before everything
- Tests (T004-T010) before implementation (T011-T022) - TDD enforcement
- Models (T011-T017) before services (T018-T021)
- Services (T018-T021) before CLI (T022) and integration (T023-T029)
- Core implementation before integration (T023-T029)
- Everything before polish (T030-T035)
- T023 blocks T019 (ChromaDB before matching)
- T024 blocks T018 (Supervision before detection)
- T027 blocks T018 and T019 (GPU before core services)

## Parallel Example
```
# Launch contract tests together (different files):
Task: "Contract test CLI interface in tests/contract/test_cli_interface.py"
Task: "Contract test processing API in tests/contract/test_processing_api.py"
Task: "Contract test supervision integration in tests/contract/test_supervision_integration.py"

# Launch model creation tasks in parallel (different files):
Task: "Contestant model in src/models/contestant.py"
Task: "FaceEmbedding model in src/models/embedding.py"
Task: "DetectedFace model in src/models/detection.py"
Task: "BoundingBox model in src/models/bbox.py"
Task: "AnnotatedFrame model in src/models/annotated_frame.py"
Task: "AnnotatedVideo model in src/models/annotated_video.py"
Task: "ProcessingStats model in src/models/processing_stats.py"

# Launch integration tests in parallel (independent scenarios):
Task: "Integration test system initialization in tests/integration/test_init.py"
Task: "Integration test video processing workflow in tests/integration/test_process.py"
Task: "Integration test status and results review in tests/integration/test_status_review.py"
Task: "Integration test edge cases in tests/integration/test_edge_cases.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Avoid: vague tasks, same file conflicts
- Each task specifies exact file path and is self-contained for LLM execution

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   - Each contract file (cli_interface.md, processing_api.md, supervision_integration.md) → contract test task [P]
   - Each CLI command/endpoint → implementation task

2. **From Data Model**:
   - Each entity (7 entities) → model creation task [P]

3. **From User Stories/Quickstart**:
   - Each scenario (init, process, status/review, edge cases) → integration test [P]

4. **Ordering**:
   - Setup → Tests → Models → Services → CLI → Integration → Polish
   - Dependencies block parallel execution

## Validation Checklist
*GATE: Checked by main() before returning*

- [x] All contracts have corresponding tests (T004-T006)
- [x] All entities have model tasks (T011-T017)
- [x] All tests come before implementation
- [x] Parallel tasks truly independent
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task