# Design: Video Player Screen

## Layout
- **Dimensions**: 1440 x 1200, Light Theme
- **Position**: Next to Video Ingestion at ~x:1416, y:4500
- **Structure**: Two-column (280px sidebar + fill main content)

## Sections

### A. Page Header (~56px)
- Title: "Video Player" + subtitle: "Face recognition playback with bounding box overlays"
- Right: Video selector dropdown showing "episode_01_performance.mp4"

### B. Player Area (horizontal, ~550px, gap 16)
- **B1 - Video Viewport** (fill, ~740px): Dark interior (#111111, 16:9), 3 green bounding boxes with name+confidence labels
- **B2 - Info Panel** (320px): Video metadata, recognition summary, current frame detections

### C. Playback Controls Bar (64px)
- Transport buttons, time display, progress bar (~22% filled), speed selector, volume

### D. Bottom Panel (horizontal, ~340px, gap 16)
- **D1 - Timeline Card** (fill): 4 contestant timeline rows with colored segments
- **D2 - Flagged Faces Card** (400px): 3 flagged detection rows

## Components to Reuse
| Component | ID | Usage |
|---|---|---|
| Sidebar | d5ZTS | Navigation |
| Sidebar Item/Active | dOLzc | "Video Player" |
| Sidebar Item/Default | X6nwq | Other nav items |
| Card | ERkuB | All card containers |
| Select Group/Default | XhJWF | Dropdowns |
| Icon Button/Default | pEY1B | Play button |
| Icon Button/Secondary | HWbHA | Transport buttons |
| Icon Button/Ghost | eNU2w | Volume |
| Progress | W4YFH | Progress bar |
| Label/Success | 7KC5U | High confidence |
| Label/Orange | L8Rgv | Medium confidence |
| Label/Secondary | it00G | Count badges |
| Avatar/Image | 4AN1p | Thumbnails |

## Sample Data
- Video: episode_01_performance.mp4, 1920x1080, 30fps, 4:32
- Current time: 1:01, Frame 1847/7230
- 3 detected faces: 王心凌 96%, 張韶涵 88%, 田馥甄 72%
- 4 timeline contestants: 王心凌, 張韶涵, 田馥甄, 陳嘉樺
