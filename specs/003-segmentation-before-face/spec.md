# Feature Specification: Segmentation-Gated Face Recognition

**Feature Branch**: `003-segmentation-before-face`  
**Created**: 2025-09-29  
**Status**: Draft  
**Input**: User description: "segmentation before face detection and recognition Exploring segmentation options I’m considering some integration points for segmentation options. One idea is to implement pre-detection person segmentation to gate detection, running it every N frames. That way, I can use masks to crop regions of interest and update the frames being processed for each ROI. Post-detection, face parsing on cropped images could mask backgrounds before embedding. But I'm unsure where the embedding is computed. If it's done inside the face detector, I’ll need to consider how to handle masking and embedding processes. It's all a bit complex! Considering embedding and tracking options I'm exploring another option where I ignore the mask for embedding but adjust acceptance for matching. There’s face tracker smoothing involved, and I think segmentation-based gating could reduce false positives and speed things up. For instance, we could propose scanning only within person masks during the face detection loop in EnhancedVideoProcessor. We should deliver a detailed plan with code reference points and pseudo-code, focusing on performance strategies like running segmentation every K frames while considering system constraints, like only processing files in the /source/videos directory. Designing segmentation integration I need to outline a clear design for integrating segmentation. First, I can add a PersonSegmenter class using an ONNX/torch model that will return a list of person masks or bounding boxes through its run(frame) method. In the EnhancedVideoProcessor, before detecting faces, I’ll get person ROIs and cache them every K frames to improve efficiency. Similar gating can be implemented in the Real-time VideoProcessor to work with masks and propagate them with the OptimizedFaceTracker. For face-level segmentation, I’ll add a FaceParser to create masks, and look into adjusting similarity thresholds based on skin ratios instead of reworking embeddings. We can propose toggles in the config.json for customization like enabling person segmentation and configuring segmentation settings. Discussing runtime and memory costs I need to address the expected runtime costs and memory usage for integrating segmentation. I can point out where the detect_faces function is called, specifically in RTVP around line 363 and Enhanced at line 1002. It's also important to mention a new caching structure that will improve efficiency. When answering the segmentation question, I should clearly state how beneficial it is and detail the integration strategy into the existing codebase, including a pseudo-code snippet. I want to keep my response concise with clear headers and bullet points, ideally 4-6 bullets per section. I won’t suggest modifications to README.md but will summarize findings related to tool activations and readings."

## Execution Flow (main)
```
1. Parse user description from Input
   → If empty: ERROR "No feature description provided"
2. Extract key concepts from description
   → Identify: actors, actions, data, constraints
3. For each unclear aspect:
   → Mark with [NEEDS CLARIFICATION: specific question]
4. Fill User Scenarios & Testing section
   → If no clear user flow: ERROR "Cannot determine user scenarios"
5. Generate Functional Requirements
   → Each requirement must be testable
   → Mark ambiguous requirements
6. Identify Key Entities (if data involved)
7. Run Review Checklist
   → If any [NEEDS CLARIFICATION]: WARN "Spec has uncertainties"
   → If implementation details found: ERROR "Remove tech details"
8. Return: SUCCESS (spec ready for planning)
```

---

## User Scenarios & Testing (mandatory)

### Primary User Story
As an operator generating recognition metadata from MV videos, I want the system to localize likely person regions first and restrict face detection to those regions, so that recognition is faster and reduces false positives in crowded scenes.

### Acceptance Scenarios
1. Given a multi-person frame, When person segmentation is enabled, Then face detection only runs within person regions and overall false positives decrease while maintaining 100% recall (no missed detections compared to baseline full-frame detection).
2. Given recognized faces with confidence scores below 0.5, When face parsing safeguards are enabled, Then the system down-weights or rejects faces with low skin-mask coverage, improving precision.
3. Given configuration `interval=K`, When processing a video, Then person segmentation executes roughly every K frames and cached ROIs are reused between intervals.
4. Given the pipeline processes only files in `/source/videos`, When batch processing runs, Then the segmentation gating is applied only to those files and outputs remain consistent with existing metadata schema.

### Edge Cases
- No person regions found: fallback to full-frame face detection to avoid misses.
- Tiny person masks (below `min_person_area`): ignore to avoid noise.
- Heavy motion/occlusion: tracker reuses cached ROIs up to 2x the segmentation interval before forcing re-segmentation or fallback to full-frame.
- Extremely dense scenes: cap maximum ROIs per frame to bound compute.

## Clarifications

### Session 2025-09-30
- Q: What is your target performance improvement with segmentation gating? → A: 10-30% faster — Modest improvement, acceptable for incremental optimization
- Q: What is the maximum acceptable recall reduction when segmentation gating is enabled? → A: No degradation allowed — Must maintain 100% of baseline recall
- Q: What should be the default value for the segmentation interval (K)? → A: 10-20 frames — Balanced approach for typical video motion
- Q: When should cached ROIs be considered stale and force a new segmentation run? → A: After 2x interval — Adaptive, directly tied to segmentation cadence
- Q: What confidence score should trigger face parsing validation? → A: < 0.5 — Only validate very uncertain detections

## Requirements (mandatory)

### Functional Requirements
- **FR-001**: System MUST provide a configuration toggle to enable/disable person segmentation gating and set cadence (`interval`, with default of 10-20 frames for balanced performance).
- **FR-002**: System MUST restrict face detection to ROI windows derived from person segmentation when gating is enabled, with fallback to full-frame when no ROI is available.
- **FR-003**: System MUST cache ROIs and reuse them between segmentation frames, invalidating after 2x the segmentation interval (adaptive TTL) or when tracker detects significant motion requiring re-segmentation.
- **FR-004**: System SHOULD support optional face-level parsing safeguards applied to detections with confidence scores below 0.5, influencing acceptance decisions (without changing embedding format).
- **FR-005**: System MUST maintain current output metadata structure; any additional quality fields MUST be additive and optional.
- **FR-006**: System MUST process only files under `/source/videos` for this feature’s scope.
- **FR-007**: System MUST expose thresholds (`min_person_area`, `expand_ratio`, `low_conf_threshold`) via configuration.
- **FR-008**: System MUST log segmentation cadence and ROI counts for observability.

### Non-Functional Requirements

- **NFR-001**: System MUST achieve 10-30% processing speed improvement compared to baseline (full-frame detection) when person segmentation gating is enabled on typical multi-person videos.
- **NFR-002**: System MUST maintain 100% recall (detection sensitivity) compared to baseline full-frame detection mode; no faces detected in baseline mode may be missed when segmentation gating is enabled.

### Key Entities

- **Segmentation Settings**: enable_person, interval (default: 10-20 frames), min_person_area, expand_ratio.
- **Face Parsing Settings**: enable_on_low_conf, low_conf_threshold (default: 0.5 for very uncertain detections).
- **ROI Cache**: keyed by frame index (or time), containing list of expanded person boxes with adaptive expiry (2x segmentation interval).

---

## Review & Acceptance Checklist

### Content Quality

- [ ] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [ ] Review checklist passed

---
