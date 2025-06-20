Face Recognition Dashboard UI Specification
Overall Layout

Viewport: Full screen application (1920x1080 recommended)
Layout: Two-column main layout with bottom panel
Color Scheme: Dark theme with blue accents
Responsive: Should adapt to different screen sizes

Component Structure
Main Container (Full Screen)
┌─────────────────────────────────────────────────────────────────┐
│ Header Bar (60px height)                                       │
├─────────────────────────────────────────────────────────────────┤
│                    Main Content Area                           │
│ ┌─────────────────────┐ ┌─────────────────────────────────────┐ │
│ │                     │ │                                     │ │
│ │   Video Player      │ │    Face Recognition Panel          │ │
│ │   (60% width)       │ │    (40% width)                     │ │
│ │                     │ │                                     │ │
│ │                     │ │                                     │ │
│ └─────────────────────┘ └─────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Similarity Scores Panel (200px height)                         │
└─────────────────────────────────────────────────────────────────┘
Component Specifications
1. Header Bar (Top - 60px height)

Background: Dark gray (#2a2a2a)
Content:

App title: "Face Recognition Dashboard" (left aligned)
Current timestamp (right aligned)
Status indicator (center) - "LIVE" badge when processing



2. Video Player Panel (Left - 60% width)

Background: Black (#000000)
Content:

Live video stream display (16:9 aspect ratio preferred)
Video controls overlay (play/pause, timeline, volume)
Detection overlay: Green bounding boxes around detected faces
Each bounding box labeled with confidence score


Features:

Full-screen toggle button
Frame rate display (bottom left corner)
Resolution indicator (bottom right corner)



3. Face Recognition Panel (Right - 40% width)

Background: Dark blue-gray (#1e293b)
Header: "Detected Faces" with count badge
Content: Grid layout of face tiles

Face Tile Specifications:

Size: 120x120px per tile
Layout: 3 columns, auto rows with 10px gap
Border: 2px solid, color-coded by confidence:

Green (#22c55e): High confidence (>90%)
Yellow (#eab308): Medium confidence (70-90%)
Red (#ef4444): Low confidence (<70%)


Content per tile:

Cropped face image (100x100px)
Name/ID label (if recognized)
Confidence percentage
Timestamp of detection


Interaction: Click to highlight corresponding detection in video

4. Similarity Scores Panel (Bottom - 200px height)

Background: Dark gray (#374151)
Title: "Recognition Confidence Scores"
Content: Horizontal bar chart showing confidence scores for each detected person
Chart Specifications:

X-axis: Person names/IDs
Y-axis: Confidence percentage (0-100%)
Bars colored same as tile borders (green/yellow/red)
Real-time updates as new faces are detected
Maximum 10 most recent detections shown



Data Flow Requirements
Input Data Structure:
json{
  "video_frame": "base64_encoded_image",
  "timestamp": "ISO_timestamp",
  "detections": [
    {
      "face_id": "unique_identifier",
      "bounding_box": {"x": 0, "y": 0, "width": 100, "height": 100},
      "face_crop": "base64_encoded_face_image",
      "recognition": {
        "name": "John Doe",
        "confidence": 0.95,
        "database_id": "person_123"
      }
    }
  ]
}
Real-time Updates:

Video frame updates: 30 FPS
Face detection updates: As new faces are detected
Similarity scores: Update every 1 second with latest data

Technical Requirements
Frontend Framework Suggestions:

React with TypeScript for component structure
WebSocket for real-time data streaming
Canvas API for video overlay drawings
Chart.js or D3.js for similarity scores visualization

Key Features to Implement:

Real-time video streaming with overlay capabilities
Dynamic face tile management (add/remove/update)
Interactive face highlighting between video and tiles
Responsive grid layout for face tiles
Animated bar chart for similarity scores
Dark theme with accessibility considerations

Performance Considerations:

Limit face tiles to maximum 50 active detections
Implement virtual scrolling for large number of faces
Optimize video rendering to prevent memory leaks
Debounce similarity score updates to prevent excessive re-renders

User Interactions

Video Panel:

Click on detection box → Highlight corresponding face tile
Double-click → Enter full-screen mode
Hover over detection → Show detailed info tooltip


Face Tiles:

Click → Highlight detection in video and show in chart
Right-click → Context menu (edit name, remove, etc.)
Hover → Show detailed recognition information


Similarity Chart:

Hover over bar → Show detailed confidence breakdown
Click bar → Focus on corresponding face tile and video detection



This specification provides clear guidance for implementation while maintaining the core functionality of your original mockup.