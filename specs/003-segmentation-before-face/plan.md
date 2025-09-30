
# Implementation Plan: Segmentation-Gated Face Recognition

**Branch**: `003-segmentation-before-face` | **Date**: 2025-09-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/Users/swong/dev/mv-face-recognition/specs/003-segmentation-before-face/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary

Implement person segmentation gating to optimize face detection performance by 10-30% while maintaining 100% recall. The system will run person segmentation every 10-20 frames, cache ROIs, and restrict face detection to person regions only. Optional face parsing safeguards will validate low-confidence detections (< 0.5) without modifying embedding format. All processing remains scoped to `/source/videos` with configurable thresholds.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: OpenCV 4.8+, NumPy 1.24+, PyTorch/ONNX Runtime (for segmentation models)
**Storage**: Local file system (`/source/videos` input, processed video outputs with metadata)
**Testing**: pytest (existing test infrastructure in mvp-processor/tests/)
**Target Platform**: Linux/macOS with optional GPU acceleration (CUDA/Metal)
**Project Type**: Video processing pipeline (Python backend + SvelteKit frontend)
**Performance Goals**: 10-30% faster face detection processing vs. baseline full-frame detection
**Constraints**: 100% recall preservation (no missed detections), maintain existing metadata schema
**Scale/Scope**: Single-video batch processing, 10-20 frame segmentation interval, ROI cache management

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: PASS (Constitution template not yet customized for this project)

**Initial Assessment**:
- Test-first approach will be followed (contract tests, integration tests before implementation)
- Changes are additive to existing video processing pipeline
- No new architectural patterns introduced (extends existing VideoProcessor)
- Observability via logging (FR-008: segmentation cadence and ROI counts)
- Configuration-driven feature flags for gradual rollout

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)

```
mvp-processor/
├── src/
│   ├── video_processor.py      # Core video frame extraction
│   ├── face_detector.py         # Face detection logic
│   ├── process_video.py         # Main processing pipeline
│   ├── person_segmenter.py     # NEW: Person segmentation module
│   ├── face_parser.py          # NEW: Face parsing for low-conf validation
│   └── roi_cache.py            # NEW: ROI caching logic
└── tests/
    ├── unit/
    │   ├── test_person_segmenter.py  # NEW
    │   ├── test_face_parser.py       # NEW
    │   └── test_roi_cache.py         # NEW
    ├── integration/
    │   └── test_segmentation_pipeline.py  # NEW
    └── contract/
        └── test_segmentation_config.py    # NEW

frontend/
└── [No changes required - metadata schema remains compatible]

worker/
└── [No changes required - API contracts unchanged]
```

**Structure Decision**: Video processing pipeline (Python backend). All new modules added to `mvp-processor/src/` to extend existing face detection pipeline. Frontend and worker unchanged as metadata schema is preserved (FR-005).

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh opencode`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach

*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:

1. **Configuration & Schema Tasks** (from config-schema.json):
   - Validate configuration schema contract test
   - Implement SegmentationConfig and FaceParsingConfig classes
   - Add config loading/validation to VideoProcessor

2. **Core Module Tasks** (from contracts/):
   - **PersonSegmenter**: Contract tests → Implementation → Integration tests
   - **ROICache**: Contract tests → Implementation → Integration tests
   - **FaceParser**: Contract tests → Implementation → Integration tests

3. **Integration Tasks** (from data-model.md):
   - Modify VideoProcessor to integrate PersonSegmenter
   - Implement segmentation-gated face detection loop
   - Add face parsing validation to detection pipeline
   - Extend metadata generator for new optional fields

4. **Testing Tasks** (from quickstart.md):
   - Baseline vs. segmentation performance benchmarks
   - Recall preservation validation tests
   - Cache performance tests
   - End-to-end pipeline integration tests

**Ordering Strategy**:

```
Phase 2A: Foundation (Parallel)
├─ [P] test_segmentation_config.py (contract test)
├─ [P] test_person_segmenter_contract.py
├─ [P] test_roi_cache_contract.py
└─ [P] test_face_parser_contract.py

Phase 2B: Core Modules (Sequential dependencies)
├─ person_segmenter.py (implement)
├─ roi_cache.py (implement)
├─ face_parser.py (implement)
└─ Verify all contract tests pass

Phase 2C: Integration (Sequential)
├─ Extend VideoProcessor with segmentation gating
├─ Modify detect_faces to use ROI cache
├─ Add face parsing validation hook
├─ Update metadata schema with optional fields
└─ Integration test (test_segmentation_pipeline.py)

Phase 2D: Validation (Parallel)
├─ [P] Performance benchmark tests
├─ [P] Recall preservation tests
└─ [P] Quickstart validation tests
```

**Task Dependencies**:
- PersonSegmenter, ROICache, FaceParser can be built in parallel (independent)
- VideoProcessor integration depends on all three modules complete
- Integration tests depend on VideoProcessor changes
- Validation tests depend on full integration complete

**Estimated Output**: 22-28 numbered, dependency-ordered tasks in tasks.md

**Key Milestones**:
- Milestone 1: All contract tests written and failing (TDD red phase)
- Milestone 2: Core modules implemented, contract tests passing (TDD green phase)
- Milestone 3: Integration complete, pipeline tests passing
- Milestone 4: Performance targets met, recall preserved (validation phase)

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking

*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
  - ✅ research.md generated (model selection, ROI cache design, face parsing approach)
  - ✅ All technical decisions documented with rationale
  - ✅ Dependencies identified (onnxruntime, YOLOv8-seg model)
- [x] Phase 1: Design complete (/plan command)
  - ✅ data-model.md generated (8 entities with validation rules)
  - ✅ contracts/ directory created with 4 contract specifications
  - ✅ quickstart.md generated (step-by-step validation guide)
  - ✅ Configuration schema defined (config-schema.json)
- [x] Phase 2: Task planning approach documented (/plan command)
  - ✅ 4-phase task strategy outlined (Foundation → Core → Integration → Validation)
  - ✅ Dependency ordering specified (22-28 tasks estimated)
  - ✅ TDD workflow defined (contract tests → implementation → integration)
- [x] Phase 3: Tasks generated (/tasks command)
  - ✅ tasks.md generated (27 numbered tasks with dependencies)
  - ✅ 4 contract test tasks (PersonSegmenter, ROICache, FaceParser, Config)
  - ✅ 3 integration test tasks (pipeline, face parsing, config toggle)
  - ✅ 6 core implementation tasks (config classes, 3 modules)
  - ✅ 4 VideoProcessor integration tasks
  - ✅ 3 logging/observability tasks
  - ✅ 4 validation/benchmark tasks
  - ✅ Parallel execution opportunities identified (14 tasks can run concurrently)
- [ ] Phase 4: Implementation complete - FUTURE
- [ ] Phase 5: Validation passed - FUTURE

**Gate Status**:
- [x] Initial Constitution Check: PASS (test-first, additive changes, observability)
- [x] Post-Design Constitution Check: PASS (no architectural changes, extends existing pipeline)
- [x] All NEEDS CLARIFICATION resolved (5 clarifications from /clarify session)
- [x] Complexity deviations documented: NONE (extends existing patterns)

**Artifacts Generated**:
- `/specs/003-segmentation-before-face/research.md` (6 research questions answered)
- `/specs/003-segmentation-before-face/data-model.md` (8 entities, state transitions, relationships)
- `/specs/003-segmentation-before-face/contracts/config-schema.json` (JSON schema validation)
- `/specs/003-segmentation-before-face/contracts/person-segmenter-contract.md` (7 contract tests)
- `/specs/003-segmentation-before-face/contracts/roi-cache-contract.md` (8 contract tests)
- `/specs/003-segmentation-before-face/contracts/face-parser-contract.md` (8 contract tests)
- `/specs/003-segmentation-before-face/quickstart.md` (8-step validation guide)
- `/specs/003-segmentation-before-face/tasks.md` (27 numbered, dependency-ordered tasks)

**Next Step**: Execute tasks from tasks.md (start with T001: Install ONNX Runtime)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*
