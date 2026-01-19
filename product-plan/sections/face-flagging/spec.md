# Face Flagging Specification

## Overview
A correction workflow where users can flag incorrect face identifications to improve recognition accuracy over time. Users review detected faces, mark misidentifications, and suggest correct contestant assignments.

## User Flows
- Browse faces pending review, grouped by video
- View a detected face alongside its current identification
- Flag a face as incorrectly identified
- Select the correct contestant from a dropdown/search
- Mark a face as "unknown" if contestant is not in database
- Submit corrections for processing
- View history of submitted corrections
- Filter faces by video, contestant, or confidence level

## UI Requirements
- Face review grid showing detected face crops with current labels
- Side-by-side comparison: detected face vs. assigned contestant photo
- Contestant selector with search and photo previews
- "Unknown person" option for unrecognized faces
- Confidence score indicator for each detection
- Filter controls for video, contestant, confidence threshold
- Correction submission form with optional notes
- Submission history table with status (pending, accepted, rejected)
- Bulk selection for flagging multiple faces at once

## Out of Scope
- Adding new contestants to the database
- Training/retraining the face recognition model directly
- Real-time correction during video playback

## Configuration
- shell: true
