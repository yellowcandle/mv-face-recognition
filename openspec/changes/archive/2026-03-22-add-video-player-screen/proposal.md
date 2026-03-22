# Proposal: Add Video Player Screen to untitled.pen

## Problem
The `untitled.pen` design file has 6 screens but is missing the Video Player — a key screen visible in the sidebar navigation. The Video Player is the core user-facing screen where users watch processed videos with real-time face recognition bounding box overlays.

## Solution
Add a complete Video Player screen to the .pen file using pencil MCP tools, matching the existing design system (light theme, 1440x1200, two-column layout with sidebar). The screen includes a video viewport with bounding boxes, info panel, playback controls, contestant timeline, and flagged detections panel.

## Scope
- Single .pen design file modification via pencil MCP batch_design calls
- Reuses existing components (sidebar, cards, buttons, labels, etc.)
- No code changes — design artifact only
