# Data Model

## Entities

### Contestant
A person who can be identified in videos. Each contestant has a photo and face embedding used for recognition. The system tracks their appearances across all processed videos.

### Video
A processed video with face recognition metadata, ready for viewing. Contains information about duration, source (YouTube URL), and processing status. Serves as the container for all face detections.

### FaceDetection
A detected face at a specific frame and timestamp within a video. Includes the bounding box coordinates, confidence score, and which contestant was identified. Used to render real-time overlays during playback.

### Flag
A user-submitted correction indicating a face was misidentified. Contains the original detection, the correct contestant, and optional notes. Used to improve recognition accuracy through embedding updates.

### ProcessingJob
A YouTube video submission queued for face detection processing. Tracks the source URL, processing status (queued, processing, completed, failed), and produces a Video when successfully completed.

## Relationships

- Video has many FaceDetections
- Contestant has many FaceDetections (appears across multiple videos)
- FaceDetection belongs to one Video and one Contestant
- Flag belongs to one FaceDetection and references the correct Contestant
- ProcessingJob produces one Video (when completed)
