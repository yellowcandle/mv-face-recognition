# MV Face Recognition

## Description
A video annotation and viewing platform that automatically identifies contestants in video content, hosts annotated videos with real-time face overlays, and provides analytics for fan communities to explore who appears when.

## Problems & Solutions

### Problem 1: Tracking appearances is tedious
Automatically detect and identify contestants using face recognition, generating frame-by-frame metadata.

### Problem 2: Recognition isn't perfect
Allow fans to flag incorrect identifications, which improves the model over time through embedding updates.

### Problem 3: No centralized place to watch with face data
Host annotated videos with real-time contestant thumbnails and bounding boxes during playback.

### Problem 4: Hard to see patterns in appearances
Analytics dashboard showing contestant screen time, co-appearances, and appearance trends.

### Problem 5: Processing videos is resource-intensive
Cloud GPU processing via Modal.com handles the heavy lifting, with optimized batching and caching.

## Key Features
- Face detection and recognition using InsightFace + ChromaDB
- YouTube video ingestion pipeline
- Hosted video player with real-time face overlays and thumbnails
- Face flagging and correction workflow
- Analytics dashboard (screen time, co-appearances, trends)
- Dense metadata generation for 60fps playback sync
- HuggingFace integration for embedding storage and sync
