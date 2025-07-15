# Requirements Document

## Introduction

The video player face overlay system needs to be fixed and enhanced to properly display face recognition overlays on videos and show a live gallery of detected faces. The current implementation shows "No faces detected" and the face recognition functionality is not working correctly. This spec addresses fixing the existing video player to properly render face overlays with bounding boxes, confidence indicators, and a side gallery of recognized contestants.

## Requirements

### Requirement 1

**User Story:** As a user, I want to see face recognition overlays directly on the video while it plays, so that I can visually identify contestants in real-time.

#### Acceptance Criteria

1. WHEN a video is playing THEN the system SHALL display bounding boxes around detected faces on the video canvas
2. WHEN a face is recognized with confidence > 0.7 THEN the system SHALL display the contestant name above the bounding box
3. WHEN a face has confidence between 0.5-0.7 THEN the system SHALL display the bounding box in orange color
4. WHEN a face has confidence > 0.7 THEN the system SHALL display the bounding box in green color
5. WHEN a face has confidence < 0.5 THEN the system SHALL display the bounding box in red color
6. WHEN the video timeline changes THEN the system SHALL update face overlays to match the current frame timestamp

### Requirement 2

**User Story:** As a user, I want to see a live gallery of faces being detected in the current video frame, so that I can see all contestants currently visible.

#### Acceptance Criteria

1. WHEN faces are detected in the current frame THEN the system SHALL display face thumbnails in a sidebar gallery
2. WHEN a face thumbnail is clicked THEN the system SHALL highlight the corresponding bounding box on the video
3. WHEN a face is recognized THEN the gallery SHALL display the contestant name and confidence score
4. WHEN no faces are detected THEN the gallery SHALL show "No faces detected" message
5. WHEN multiple faces are detected THEN the gallery SHALL sort faces by confidence score (highest first)

### Requirement 3

**User Story:** As a user, I want to filter and search through detected faces, so that I can focus on specific contestants.

#### Acceptance Criteria

1. WHEN I type in the search box THEN the system SHALL filter faces by contestant name
2. WHEN I select "Selected Only" filter THEN the system SHALL show only faces I have clicked on
3. WHEN I change the sort option THEN the system SHALL reorder faces by confidence or name
4. WHEN I clear filters THEN the system SHALL show all detected faces again

### Requirement 4

**User Story:** As a user, I want the video player to load and display face recognition data correctly, so that the system works as intended.

#### Acceptance Criteria

1. WHEN a video is selected THEN the system SHALL load the corresponding metadata JSON file
2. WHEN metadata is loaded THEN the system SHALL parse face detection data for each frame
3. WHEN video playback starts THEN the system SHALL synchronize face overlays with video timeline
4. WHEN metadata loading fails THEN the system SHALL display an appropriate error message
5. WHEN no metadata exists for a video THEN the system SHALL show "No face data available" message

### Requirement 5

**User Story:** As a user, I want the face overlay rendering to be smooth and performant, so that video playback is not interrupted.

#### Acceptance Criteria

1. WHEN video is playing THEN face overlays SHALL update at 60fps without stuttering
2. WHEN multiple faces are detected THEN the system SHALL render all overlays without performance degradation
3. WHEN the video player is resized THEN face overlays SHALL scale proportionally
4. WHEN switching between videos THEN the system SHALL clear previous overlays and load new data
5. WHEN video playback is paused THEN face overlays SHALL remain visible and accurate

### Requirement 6

**User Story:** As a user, I want interactive face detection features, so that I can explore face recognition results in detail.

#### Acceptance Criteria

1. WHEN I hover over a face bounding box THEN the system SHALL highlight the face and show detailed information
2. WHEN I click on a face bounding box THEN the system SHALL select the face and update the gallery
3. WHEN I hover over a face in the gallery THEN the system SHALL highlight the corresponding video overlay
4. WHEN I click on a face in the gallery THEN the system SHALL focus on that face in the video
5. WHEN face details are shown THEN the system SHALL display contestant name, confidence score, and frame timestamp