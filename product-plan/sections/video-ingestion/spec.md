# Video Ingestion Specification

## Overview
An admin interface for submitting YouTube URLs, monitoring processing status, and managing the video library. Users can add new videos for processing, track their progress through the face recognition pipeline, and view/manage existing videos.

## User Flows
- Submit a YouTube URL for processing
- View processing queue with status indicators (pending, processing, completed, failed)
- Monitor progress of videos currently being processed
- View list of all processed videos with metadata
- Retry failed video processing
- Delete videos from the library
- View processing logs/details for troubleshooting

## UI Requirements
- URL input form with validation for YouTube links
- Processing queue table showing status, progress percentage, timestamps
- Status badges (pending, processing, completed, failed)
- Progress bar for videos currently processing
- Video library list with title, duration, date added, face count
- Action buttons for retry, delete, view details
- Processing log viewer/modal for debugging
- Empty state for when no videos are in queue

## Out of Scope
- Batch URL upload
- Scheduling/delayed processing
- Video editing or re-processing partial segments
- Direct file upload (YouTube URLs only)

## Configuration
- shell: true
