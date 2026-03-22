# Tasks: Add Video Player Screen

## Implementation Tasks

- [x] 1. Create top-level frame (1440x1200, placeholder:true), copy sidebar from existing screen, update active nav item to "Video Player"
- [x] 2. Add page header with title "Video Player", subtitle, and video selector dropdown
- [x] 3. Build video viewport card with dark interior (#111111, 16:9 ratio) and 3 green bounding boxes with name+confidence labels (王心凌 96%, 張韶涵 88%, 田馥甄 72%) plus frame counter overlay
- [x] 4. Build info panel card (320px) with video metadata section, recognition summary stats, and current frame detections list
- [x] 5. Add playback controls bar with transport buttons (skip-5s, prev-frame, play/pause, next-frame, skip+5s), time display, progress bar (~22% filled), speed selector, and volume button
- [x] 6. Build timeline card with header "Contestant Timeline", filter dropdown, and 4 contestant timeline rows with colored segments and playhead marker
- [x] 7. Build flagged faces card (400px) with header "Flagged Detections", count badge "3", and 3 flagged detection rows with thumbnail+name+timestamp+confidence; remove placeholder flag from top-level frame
