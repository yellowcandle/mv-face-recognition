# TODOS

## Post-InsightFace Swap

### Tune tolerance threshold
- **What:** Run test-video-mv2 with InsightFace, collect distance distribution, tune `tolerance` in `processing_config.yaml`
- **Why:** Starting at 0.4 (cosine distance) as default. Optimal value depends on actual data. InsightFace same-person matches are typically 0.1-0.3, cross-person 0.5-1.5. Sweet spot usually 0.35-0.45.
- **Depends on:** InsightFace swap landing first
- **Added:** 2026-03-23 via /plan-eng-review

## Post-Supervision Integration

### Fixed color assignment for contestants
- **What:** Assign each contestant a stable, fixed color across all videos (vs dynamic per-tracker colors)
- **Why:** Fans would learn to associate specific colors with contestants. Currently using `class_id % palette_size` which cycles through a small palette. For 96 contestants with only ~10 on screen at a time, a 20-color palette with modular assignment works but may have collisions.
- **Options:** (a) Use contestant_id-based fixed colors via class_id. (b) Use a perceptually-distinct palette of 20 colors and accept collisions. (c) Use contestant's theme color if one exists.
- **Depends on:** Supervision integration landing first
- **Added:** 2026-03-23 via /plan-eng-review

### ~~Fix timeline bar "TOP" error~~ FIXED
- **Fixed:** 2026-03-23 — Two issues: (1) CJK text rendered via cv2.putText which can't display Chinese → switched to PIL+PingFang. (2) screen_time accumulated from ByteTrack tracked labels which drops custom data → accumulate from original sv_detections labels instead.

### ~~Fix bbox displaying early (ahead of face position)~~ FIXED
- **Fixed:** 2026-03-23 — Changed from nearest-timestamp matching (bisect_left + neighbor comparison) to floor-only matching (bisect_right, pick idx-1). Bboxes now only appear after the detection, never before.
