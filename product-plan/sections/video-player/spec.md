# Video Player Specification

## Overview
An interactive video player that displays processed videos with real-time face recognition overlays. Users can browse videos from a sidebar list, watch with bounding boxes and contestant thumbnails, and filter the timeline to jump to specific contestant appearances.

## User Flows
- Browse and select videos from sidebar list
- Play/pause, stop, and control playback speed (0.25x - 2x)
- Skip forward/backward by frames or seconds
- View bounding boxes around detected faces during playback
- See contestant thumbnails showing who's currently on screen
- Click a face or thumbnail to view contestant card popup
- Filter timeline to show moments where a specific contestant appears
- Jump to filtered timestamps

## UI Requirements
- Video player with standard controls (play/pause, stop, progress bar)
- Frame skip and second skip buttons (+/- controls)
- Playback speed selector (0.25x, 0.5x, 1x, 1.5x, 2x)
- Face bounding box overlays synced to video playback
- Contestant thumbnail strip below/beside video
- Contestant card popup with photo, name, profile link
- Video sidebar list for browsing available videos
- Contestant filter dropdown to filter timeline
- Timeline markers showing filtered contestant appearances

## Out of Scope
- Comments, reactions, or social features
- Video editing, trimming, or export
- Live streaming support

## Configuration
- shell: true
