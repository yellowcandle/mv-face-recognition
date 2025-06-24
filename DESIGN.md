# MV Face Recognition - Design Document

## Overview

This document describes the architecture and design decisions for the clean rewrite of the MV Face Recognition system. The system processes video files for face recognition, specifically targeting videos in the `/source/videos/` directory.

## Architecture

### Core Requirements

- **No webcam processing**: Only process video files from `/source/videos/` directory
- **Preserve existing data**: Keep `/source/photo/contestants/` with existing photos and embeddings
- **Preserve documentation**: Keep `/docs/` functionality and README.md intact
- **Use ChromaDB**: For fast similarity search of face embeddings

### System Components

```
app.py (Streamlit UI)
├── src/
│   ├── core/
│   │   ├── face_detector.py (InsightFace detection)
│   │   └── face_matcher.py (ChromaDB similarity search)
│   ├── services/
│   │   └── video_processor.py (Video processing pipeline)
│   └── database/
│       └── chroma_setup.py (ChromaDB management)
├── config.json (Configuration)
├── requirements.txt (Minimal dependencies)
└── data/ (Generated ChromaDB storage)
```

## Technology Stack

### Core Technologies
- **Streamlit**: Web interface for video processing
- **InsightFace**: Face detection and embedding generation
- **ChromaDB**: Vector database for fast similarity search
- **OpenCV**: Video processing and image manipulation
- **PyTorch**: Deep learning backend

### Key Dependencies
```
streamlit>=1.28.0      # Web interface
insightface>=0.7.3     # Face detection/recognition
chromadb>=0.4.0        # Vector database
opencv-python>=4.8.0   # Video/image processing
torch>=2.0.0           # ML backend
```

## Design Decisions

### 1. Frontend Choice: NiceGUI

**Decision**: Use NiceGUI for a modern, real-time Python-based UI.

**Rationale**:
- **Modern UI with Python**: Allows for the creation of a modern, responsive UI with Material Design components, all within Python.
- **Real-time Updates**: Built-in support for WebSockets and server-sent events enables live updates for features like real-time processing previews and dashboards.
- **Performance**: No page reloads, leading to a smoother and more responsive user experience compared to Streamlit.
- **Flexibility**: Offers more control over layout and components than Streamlit or Gradio, allowing for a more professional and customized application.
- **Async Support**: Integrates well with asynchronous backend tasks, which is ideal for video processing.

**Alternatives Considered**:
- **Streamlit**: Good for rapid prototyping and data-heav-y applications, but less flexible for custom UI and real-time interactivity.
- **PyQt6**: Powerful for desktop applications, but requires more boilerplate code and is not web-native.
- **React/Vue + FastAPI**: Offers maximum flexibility but requires separate frontend and backend development, increasing complexity.

### 2. Database Choice: ChromaDB

**Decision**: Use ChromaDB for vector similarity search

**Rationale**:
- Significantly faster than numpy-based similarity search for 96+ contestants
- Persistent storage eliminates need to reload embeddings on each run
- Built-in similarity thresholding and result limiting
- Excellent performance for batch processing of video frames

**Performance Comparison**:
- Numpy dot product: O(n) for each query, ~5ms for 96 contestants
- ChromaDB: ~1ms for each query with built-in optimizations

### 3. Video Processing Strategy

**Decision**: Frame-by-frame processing with configurable skip intervals

**Architecture**:
```python
def process_video():
    for frame_num, frame in extract_frames(skip=5):
        faces = detect_faces(frame)
        for face in faces:
            embedding = face['embedding']
            match = match_face(embedding)  # ChromaDB search
            annotate_frame(frame, face, match)
```

**Benefits**:
- Memory efficient (process one frame at a time)
- Configurable frame skip for speed vs accuracy trade-off
- Real-time progress tracking
- Handles videos of any length

### 4. Configuration Management

**Decision**: Single JSON configuration file

**Structure**:
```json
{
    "face_detection": {
        "model_name": "buffalo_l",
        "detection_threshold": 0.5,
        "input_size": [640, 640]
    },
    "face_matching": {
        "similarity_threshold": 0.6,
        "max_results": 5
    },
    "video_processing": {
        "frame_skip": 5,
        "output_fps": 24
    }
}
```

**Benefits**:
- Runtime configuration changes through UI
- Easy to backup and restore settings
- Clear separation of concerns

## Data Flow

### 1. System Initialization
```
1. Load config.json
2. Initialize InsightFace model (buffalo_l)
3. Load existing .npy embeddings into ChromaDB
4. Launch Streamlit interface
```

### 2. Video Processing Pipeline
```
1. User selects video from /source/videos/
2. Configure processing parameters (time range, thresholds)
3. Extract frames with configurable skip interval
4. For each frame:
   a. Detect faces using InsightFace
   b. Extract embeddings for detected faces
   c. Search ChromaDB for similar faces
   d. Record matches above similarity threshold
5. Generate results summary and optional outputs:
   a. Annotated video with bounding boxes and names
   b. CSV file with detailed frame-by-frame results
```

### 3. Data Structures

**Face Detection Result**:
```python
{
    'bbox': [x1, y1, x2, y2],
    'confidence': 0.95,
    'landmarks': [[x, y], ...],
    'embedding': np.array([512 dimensions])
}
```

**Recognition Result**:
```python
{
    'matched': True,
    'contestant_name': 'Alice',
    'similarity_score': 0.85,
    'confidence_level': 'high'
}
```

## Performance Optimizations

### 1. ChromaDB Vector Search
- Pre-populated database eliminates embedding reload overhead
- Cosine similarity search optimized for 512-dimensional embeddings
- Configurable similarity thresholds reduce false positives

### 2. Video Processing
- Frame skipping reduces processing time (5x speedup with skip=5)
- Memory-efficient single-frame processing
- Optional time range selection for targeted analysis

### 3. Caching Strategy
- ChromaDB provides persistent storage
- Embedding cache in face matcher for repeated queries
- Video metadata cached for UI responsiveness

## Error Handling

### 1. Graceful Degradation
- Missing videos: Clear error messages with available alternatives
- Face detection failures: Continue processing other frames
- ChromaDB connection issues: Fallback to numpy-based matching

### 2. User Feedback
- Progress bars for long-running operations
- Detailed error messages with suggested solutions
- System status indicators in UI

## Security Considerations

### 1. File Access
- Restricted to `/source/videos/` directory only
- No arbitrary file system access
- Input validation for video file types

### 2. Configuration
- Bounded input ranges for all parameters
- Validation of configuration values
- Safe defaults for all settings

## Extensibility

### 1. Adding New Detection Models
```python
# Easy to swap InsightFace models
class FaceDetector:
    def __init__(self, model_name="buffalo_l"):
        self.app = FaceAnalysis(name=model_name)
```

### 2. Alternative Databases
```python
# ChromaDB manager can be replaced
class VectorDatabase:
    def search_similar_faces(self, embedding):
        pass  # Interface for other vector databases
```

### 3. Output Formats
- CSV export already implemented
- JSON export can be easily added
- Integration with external systems via API

## Testing Strategy

### 1. Unit Tests
- Face detection accuracy with known images
- ChromaDB embedding storage and retrieval
- Video frame extraction validation

### 2. Integration Tests
- End-to-end video processing pipeline
- Configuration persistence and loading
- UI component functionality

### 3. Performance Tests
- Video processing speed benchmarks
- Memory usage monitoring
- ChromaDB query performance

## Deployment

### 1. Local Development
```bash
uv sync                    # Install dependencies
streamlit run app.py       # Launch application
```

### 2. Production Considerations
- Docker containerization possible
- GPU acceleration for InsightFace
- Horizontal scaling for batch processing

## Future Enhancements

### 1. Real-time Processing
- Live video stream processing
- Webcam integration (if requirements change)

### 2. Advanced Analytics
- Contestant appearance timelines
- Co-appearance analysis
- Confidence score distributions

### 3. Export Options
- Video highlights generation
- Automated report generation
- Integration with external databases

## Changelog

### v1.0.0 - Clean Rewrite (2024-06-23)
- Complete rewrite from scratch
- Streamlit-based interface
- ChromaDB integration for fast similarity search
- Support for 5 MV videos in `/source/videos/`
- 96 contestants with pre-computed embeddings
- Configurable processing parameters
- CSV and annotated video export

## Dependencies

See `requirements.txt` for the complete list of dependencies. Key libraries:

- **streamlit**: Web interface framework
- **insightface**: Face detection and recognition
- **chromadb**: Vector database for similarity search
- **opencv-python**: Video and image processing
- **torch**: Machine learning framework
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computing
- **tqdm**: Progress bars
- **ffmpeg-python**: Video processing utilities

---

# Comprehensive Claude Code Prompt: Migrating Complex Face Recognition Application from Gradio to Vue.js

## Overview
You are tasked with creating a comprehensive migration guide and implementation strategy for converting a sophisticated Gradio-based face recognition web application to a modern Vue.js frontend. This system features real-time video processing, multi-tab interfaces, interactive data visualizations, and complex state management.

## Current System Analysis
The existing application includes:
- Multi-tab interface (Video Processing, Settings, UMAP Visualization, Similarity Analysis, Analytics)
- Real-time video processing with face recognition capabilities
- File upload system for videos and images
- Interactive data visualizations (UMAP plots, similarity charts, timelines)
- Complex state management for processing workflows
- Python backend services (FaceDetector, RecognitionService, VideoProcessingService, VisualizationService)
- Advanced UI features (progress tracking, data tables, charts, real-time updates)

## Recommended Technology Stack

### Frontend Stack
- **Framework**: Vue.js 3 with Composition API
- **State Management**: Pinia (modern, TypeScript-native alternative to Vuex)
- **UI Framework**: Vuetify 3 (Material Design 3) for professional applications, or Quasar Framework for high-performance needs
- **Build Tool**: Vite (faster development, better tree-shaking than Webpack)
- **HTTP Client**: Axios with interceptors for error handling and authentication
- **Real-time Communication**: WebSocket API with Socket.IO client
- **Charts & Visualization**: 
  - D3.js for custom UMAP visualizations
  - vue-chartjs for standard charts
  - ECharts for performance-critical large datasets
- **Testing**: Vitest for unit testing, Cypress for E2E testing
- **TypeScript**: Full TypeScript integration for type safety

### Backend Integration
- **API Framework**: FastAPI (recommended) or Flask with Flask-SocketIO
- **Authentication**: JWT tokens with refresh token strategy
- **File Upload**: Multipart form data with progress tracking
- **Real-time Updates**: WebSocket connections for processing status
- **Background Tasks**: Celery with Redis for long-running video processing

## Project Structure Recommendations

```
src/
├── core/                          # Shared core functionality
│   ├── components/                # Reusable UI components
│   │   ├── ui/                   # Basic UI elements (buttons, inputs)
│   │   ├── layout/               # Layout components (header, sidebar)
│   │   └── common/               # Common business components
│   ├── composables/              # Shared business logic
│   │   ├── useAuth.js           # Authentication logic
│   │   ├── useWebSocket.js      # WebSocket management
│   │   └── useFileUpload.js     # File upload handling
│   ├── services/                 # API service layer
│   │   ├── api.js               # Axios configuration
│   │   ├── authService.js       # Authentication API
│   │   └── recognitionService.js # Face recognition API
│   ├── utils/                    # Utility functions
│   └── types/                    # TypeScript type definitions
├── modules/                       # Feature-based modules
│   ├── video-processing/         # Video processing module
│   │   ├── components/
│   │   ├── composables/
│   │   ├── services/
│   │   ├── views/
│   │   └── store/
│   ├── face-recognition/         # Face recognition module
│   ├── data-visualization/       # Charts and analytics
│   ├── settings/                 # Application settings
│   └── user-management/          # User management
├── router/                       # Vue Router configuration
├── stores/                       # Pinia stores
├── assets/                       # Static assets
└── App.vue                       # Root component
```

## Step-by-Step Migration Approach

### Phase 1: Foundation Setup (Week 1-2)

#### 1. Project Initialization
```bash
# Create Vue 3 project with Vite
npm create vue@latest face-recognition-app
cd face-recognition-app

# Install dependencies
npm install pinia axios socket.io-client
npm install -D @types/node vitest cypress
npm install vuetify @mdi/font # or chosen UI framework
```

#### 2. Configure Build Tools
```javascript
// vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@/modules': resolve(__dirname, 'src/modules')
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'pinia', 'axios'],
          charts: ['d3', 'chart.js'],
          ui: ['vuetify']
        }
      }
    }
  }
})
```

#### 3. Setup Core Services
```javascript
// src/core/services/api.js
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const apiClient = axios.create({
  baseURL: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor for auth
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      await authStore.refreshToken()
      return apiClient.request(error.config)
    }
    return Promise.reject(error)
  }
)

export default apiClient
```

### Phase 2: Core Component Migration (Week 3-6)

#### 1. State Management with Pinia
```javascript
// src/stores/faceRecognition.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useFaceRecognitionStore = defineStore('faceRecognition', () => {
  // State
  const processingQueue = ref([])
  const currentModel = ref(null)
  const results = ref(new Map())
  const isProcessing = ref(false)
  const processingProgress = ref(0)
  
  // Getters
  const queueLength = computed(() => processingQueue.value.length)
  const hasResults = computed(() => results.value.size > 0)
  
  // Actions
  const addToQueue = (videoFile) => {
    const job = {
      id: Date.now(),
      file: videoFile,
      status: 'queued',
      createdAt: new Date()
    }
    processingQueue.value.push(job)
    return job.id
  }
  
  const processVideo = async (jobId) => {
    try {
      isProcessing.value = true
      const job = processingQueue.value.find(j => j.id === jobId)
      
      if (!job) throw new Error('Job not found')
      
      job.status = 'processing'
      
      // Upload and process video
      const formData = new FormData()
      formData.append('video', job.file)
      
      const response = await apiClient.post('/process-video', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          processingProgress.value = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
        }
      })
      
      // Store results
      results.value.set(jobId, response.data)
      job.status = 'completed'
      
    } catch (error) {
      const job = processingQueue.value.find(j => j.id === jobId)
      if (job) job.status = 'error'
      throw error
    } finally {
      isProcessing.value = false
      processingProgress.value = 0
    }
  }
  
  const clearResults = () => {
    results.value.clear()
  }
  
  return {
    processingQueue,
    currentModel,
    results,
    isProcessing,
    processingProgress,
    queueLength,
    hasResults,
    addToQueue,
    processVideo,
    clearResults
  }
})
```

#### 2. File Upload Component
```vue
<!-- src/modules/video-processing/components/VideoUpload.vue -->
<template>
  <div class="video-upload">
    <v-card>
      <v-card-title>Upload Video for Processing</v-card-title>
      <v-card-text>
        <div
          class="drop-zone"
          :class="{ 'drag-over': isDragOver }"
          @drop="handleDrop"
          @dragover.prevent="isDragOver = true"
          @dragleave="isDragOver = false"
        >
          <v-icon size="64" color="primary">mdi-cloud-upload</v-icon>
          <p>Drop video files here or click to browse</p>
          <v-btn color="primary" @click="$refs.fileInput.click()">
            Choose Files
          </v-btn>
          <input
            ref="fileInput"
            type="file"
            hidden
            multiple
            accept="video/*"
            @change="handleFileSelect"
          >
        </div>
        
        <!-- Upload Progress -->
        <div v-if="uploadProgress > 0" class="mt-4">
          <v-progress-linear
            :value="uploadProgress"
            height="20"
            striped
            color="primary"
          >
            <template v-slot:default="{ value }">
              <strong>{{ Math.ceil(value) }}%</strong>
            </template>
          </v-progress-linear>
        </div>
        
        <!-- File List -->
        <v-list v-if="selectedFiles.length > 0" class="mt-4">
          <v-list-item
            v-for="(file, index) in selectedFiles"
            :key="index"
          >
            <v-list-item-content>
              <v-list-item-title>{{ file.name }}</v-list-item-title>
              <v-list-item-subtitle>
                {{ formatFileSize(file.size) }}
              </v-list-item-subtitle>
            </v-list-item-content>
            <v-list-item-action>
              <v-btn
                icon
                @click="removeFile(index)"
              >
                <v-icon>mdi-delete</v-icon>
              </v-btn>
            </v-list-item-action>
          </v-list-item>
        </v-list>
      </v-card-text>
      
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          color="primary"
          :disabled="selectedFiles.length === 0 || isUploading"
          :loading="isUploading"
          @click="uploadFiles"
        >
          Process Videos
        </v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useFaceRecognitionStore } from '@/stores/faceRecognition'
import { useFileUpload } from '@/core/composables/useFileUpload'

const faceRecognitionStore = useFaceRecognitionStore()
const { uploadProgress, isUploading, formatFileSize } = useFileUpload()

const selectedFiles = ref([])
const isDragOver = ref(false)

const handleDrop = (event) => {
  event.preventDefault()
  isDragOver.value = false
  const files = Array.from(event.dataTransfer.files)
  addFiles(files)
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  addFiles(files)
}

const addFiles = (files) => {
  const videoFiles = files.filter(file => file.type.startsWith('video/'))
  selectedFiles.value.push(...videoFiles)
}

const removeFile = (index) => {
  selectedFiles.value.splice(index, 1)
}

const uploadFiles = async () => {
  isUploading.value = true
  
  try {
    for (const file of selectedFiles.value) {
      const jobId = faceRecognitionStore.addToQueue(file)
      await faceRecognitionStore.processVideo(jobId)
    }
    
    selectedFiles.value = []
    emit('upload-complete')
  } catch (error) {
    console.error('Upload failed:', error)
  } finally {
    isUploading.value = false
  }
}

const emit = defineEmits(['upload-complete'])
</script>

<style scoped>
.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  transition: all 0.3s ease;
}

.drop-zone.drag-over {
  border-color: #1976d2;
  background-color: #f3f8ff;
}
</style>
```

#### 3. Real-time WebSocket Integration
```javascript
// src/core/composables/useWebSocket.js
import { ref, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

export function useWebSocket(url) {
  const socket = ref(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  
  const connect = () => {
    socket.value = io(url, {
      transports: ['websocket'],
      upgrade: false
    })
    
    socket.value.on('connect', () => {
      isConnected.value = true
      reconnectAttempts.value = 0
    })
    
    socket.value.on('disconnect', () => {
      isConnected.value = false
      attemptReconnect()
    })
    
    socket.value.on('processing_update', (data) => {
      // Handle processing updates
      const faceRecognitionStore = useFaceRecognitionStore()
      faceRecognitionStore.processingProgress = data.progress
    })
    
    socket.value.on('processing_complete', (data) => {
      // Handle completion
      const faceRecognitionStore = useFaceRecognitionStore()
      faceRecognitionStore.results.set(data.jobId, data.results)
    })
  }
  
  const attemptReconnect = () => {
    if (reconnectAttempts.value < maxReconnectAttempts) {
      reconnectAttempts.value++
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.value), 30000)
      
      setTimeout(() => {
        connect()
      }, delay)
    }
  }
  
  const disconnect = () => {
    if (socket.value) {
      socket.value.disconnect()
    }
  }
  
  const emit = (event, data) => {
    if (socket.value && isConnected.value) {
      socket.value.emit(event, data)
    }
  }
  
  onMounted(() => {
    connect()
  })
  
  onUnmounted(() => {
    disconnect()
  })
  
  return {
    socket,
    isConnected,
    emit,
    connect,
    disconnect
  }
}
```

### Phase 3: Advanced Visualization Features (Week 7-10)

#### 1. UMAP Visualization Component
```vue
<!-- src/modules/data-visualization/components/UMAPVisualization.vue -->
<template>
  <div class="umap-visualization">
    <v-card>
      <v-card-title>
        UMAP Visualization
        <v-spacer></v-spacer>
        <v-btn-toggle v-model="viewMode" mandatory>
          <v-btn value="2d">2D</v-btn>
          <v-btn value="3d">3D</v-btn>
        </v-btn-toggle>
      </v-card-title>
      
      <v-card-text>
        <div ref="umapContainer" class="umap-container"></div>
        
        <!-- Controls -->
        <div class="controls mt-4">
          <v-row>
            <v-col cols="12" md="4">
              <v-select
                v-model="colorBy"
                :items="colorOptions"
                label="Color by"
                @change="updateVisualization"
              ></v-select>
            </v-col>
            <v-col cols="12" md="4">
              <v-slider
                v-model="pointSize"
                label="Point Size"
                min="1"
                max="10"
                @input="updateVisualization"
              ></v-slider>
            </v-col>
            <v-col cols="12" md="4">
              <v-slider
                v-model="opacity"
                label="Opacity"
                min="0.1"
                max="1"
                step="0.1"
                @input="updateVisualization"
              ></v-slider>
            </v-col>
          </v-row>
        </div>
        
        <!-- Selection Info -->
        <div v-if="selectedPoints.length > 0" class="selection-info mt-4">
          <v-card>
            <v-card-title>Selected Points: {{ selectedPoints.length }}</v-card-title>
            <v-card-text>
              <v-list>
                <v-list-item
                  v-for="point in selectedPoints.slice(0, 5)"
                  :key="point.id"
                >
                  <v-list-item-content>
                    <v-list-item-title>{{ point.label }}</v-list-item-title>
                    <v-list-item-subtitle>
                      Confidence: {{ point.confidence?.toFixed(3) }}
                    </v-list-item-subtitle>
                  </v-list-item-content>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  data: {
    type: Array,
    required: true
  }
})

const umapContainer = ref(null)
const viewMode = ref('2d')
const colorBy = ref('cluster')
const pointSize = ref(3)
const opacity = ref(0.7)
const selectedPoints = ref([])

const colorOptions = [
  { title: 'Cluster', value: 'cluster' },
  { title: 'Confidence', value: 'confidence' },
  { title: 'Person', value: 'person' }
]

let svg = null
let zoom = null

const initializeVisualization = () => {
  if (!umapContainer.value) return
  
  // Clear existing visualization
  d3.select(umapContainer.value).selectAll('*').remove()
  
  const width = umapContainer.value.clientWidth
  const height = 500
  
  svg = d3.select(umapContainer.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
  
  // Create zoom behavior
  zoom = d3.zoom()
    .scaleExtent([0.5, 10])
    .on('zoom', (event) => {
      svg.select('.plot-area').attr('transform', event.transform)
    })
  
  svg.call(zoom)
  
  // Create plot area
  const plotArea = svg.append('g').attr('class', 'plot-area')
  
  updateVisualization()
}

const updateVisualization = () => {
  if (!svg || !props.data) return
  
  const width = umapContainer.value.clientWidth
  const height = 500
  const margin = { top: 20, right: 20, bottom: 20, left: 20 }
  
  // Scales
  const xScale = d3.scaleLinear()
    .domain(d3.extent(props.data, d => d.x))
    .range([margin.left, width - margin.right])
  
  const yScale = d3.scaleLinear()
    .domain(d3.extent(props.data, d => d.y))
    .range([height - margin.bottom, margin.top])
  
  // Color scale
  const colorScale = d3.scaleOrdinal(d3.schemeCategory10)
  
  // Select plot area
  const plotArea = svg.select('.plot-area')
  
  // Bind data
  const points = plotArea.selectAll('.point')
    .data(props.data, d => d.id)
  
  // Enter selection
  points.enter()
    .append('circle')
    .attr('class', 'point')
    .attr('r', pointSize.value)
    .attr('cx', d => xScale(d.x))
    .attr('cy', d => yScale(d.y))
    .attr('fill', d => colorScale(d[colorBy.value]))
    .attr('opacity', opacity.value)
    .style('cursor', 'pointer')
    .on('click', function(event, d) {
      const isSelected = selectedPoints.value.includes(d)
      if (isSelected) {
        selectedPoints.value = selectedPoints.value.filter(p => p.id !== d.id)
        d3.select(this).attr('stroke', null)
      } else {
        selectedPoints.value.push(d)
        d3.select(this).attr('stroke', '#333').attr('stroke-width', 2)
      }
    })
    .on('mouseover', function(event, d) {
      // Show tooltip
      const tooltip = d3.select('body').append('div')
        .attr('class', 'tooltip')
        .style('opacity', 0)
        .style('position', 'absolute')
        .style('background', 'rgba(0, 0, 0, 0.8)')
        .style('color', 'white')
        .style('padding', '8px')
        .style('border-radius', '4px')
        .style('pointer-events', 'none')
      
      tooltip.transition()
        .duration(200)
        .style('opacity', 0.9)
      
      tooltip.html(`
        <strong>${d.label || 'Unknown'}</strong><br/>
        Confidence: ${d.confidence?.toFixed(3) || 'N/A'}<br/>
        Cluster: ${d.cluster || 'N/A'}
      `)
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 28) + 'px')
    })
    .on('mouseout', function() {
      d3.selectAll('.tooltip').remove()
    })
  
  // Update existing points
  points.transition()
    .duration(300)
    .attr('r', pointSize.value)
    .attr('fill', d => colorScale(d[colorBy.value]))
    .attr('opacity', opacity.value)
  
  // Remove old points
  points.exit().remove()
}

// Watch for data changes
watch(() => props.data, () => {
  nextTick(() => {
    updateVisualization()
  })
}, { deep: true })

// Watch for control changes
watch([viewMode, colorBy, pointSize, opacity], () => {
  updateVisualization()
})

onMounted(() => {
  nextTick(() => {
    initializeVisualization()
  })
})
</script>

<style scoped>
.umap-container {
  width: 100%;
  height: 500px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.controls {
  border-top: 1px solid #e0e0e0;
  padding-top: 16px;
}

.selection-info {
  max-height: 200px;
  overflow-y: auto;
}
</style>
```

#### 2. Multi-Tab Interface Implementation
```vue
<!-- src/views/MainInterface.vue -->
<template>
  <div class="main-interface">
    <v-app-bar app color="primary" dark>
      <v-app-bar-title>Face Recognition System</v-app-bar-title>
      <v-spacer></v-spacer>
      <v-btn icon @click="toggleTheme">
        <v-icon>mdi-theme-light-dark</v-icon>
      </v-btn>
    </v-app-bar>
    
    <v-main>
      <v-container fluid>
        <v-tabs
          v-model="activeTab"
          background-color="transparent"
          color="primary"
          grow
        >
          <v-tab
            v-for="tab in tabs"
            :key="tab.id"
            :value="tab.id"
          >
            <v-icon left>{{ tab.icon }}</v-icon>
            {{ tab.label }}
          </v-tab>
        </v-tabs>
        
        <v-tabs-window v-model="activeTab">
          <v-tabs-window-item
            v-for="tab in tabs"
            :key="tab.id"
            :value="tab.id"
          >
            <KeepAlive>
              <component
                :is="tab.component"
                v-bind="tab.props"
                @tab-data-change="handleTabDataChange"
              />
            </KeepAlive>
          </v-tabs-window-item>
        </v-tabs-window>
      </v-container>
    </v-main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useTheme } from 'vuetify'

// Lazy load tab components
const VideoProcessingTab = defineAsyncComponent(() => 
  import('@/modules/video-processing/views/VideoProcessingTab.vue')
)
const SettingsTab = defineAsyncComponent(() => 
  import('@/modules/settings/views/SettingsTab.vue')
)
const UMAPVisualizationTab = defineAsyncComponent(() => 
  import('@/modules/data-visualization/views/UMAPVisualizationTab.vue')
)
const SimilarityAnalysisTab = defineAsyncComponent(() => 
  import('@/modules/similarity-analysis/views/SimilarityAnalysisTab.vue')
)
const AnalyticsTab = defineAsyncComponent(() => 
  import('@/modules/analytics/views/AnalyticsTab.vue')
)

const theme = useTheme()
const activeTab = ref('video-processing')

const tabs = computed(() => [
  {
    id: 'video-processing',
    label: 'Video Processing',
    icon: 'mdi-video',
    component: VideoProcessingTab,
    props: {}
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: 'mdi-cog',
    component: SettingsTab,
    props: {}
  },
  {
    id: 'umap-visualization',
    label: 'UMAP Visualization',
    icon: 'mdi-chart-scatter-plot',
    component: UMAPVisualizationTab,
    props: {}
  },
  {
    id: 'similarity-analysis',
    label: 'Similarity Analysis',
    icon: 'mdi-compare',
    component: SimilarityAnalysisTab,
    props: {}
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: 'mdi-chart-line',
    component: AnalyticsTab,
    props: {}
  }
])

const toggleTheme = () => {
  theme.global.name.value = theme.global.current.value.dark ? 'light' : 'dark'
}

const handleTabDataChange = (data) => {
  // Handle cross-tab data communication
  console.log('Tab data changed:', data)
}
</script>
```

### Phase 4: Performance Optimization & Testing (Week 11-12)

#### 1. Performance Optimizations
```javascript
// src/core/composables/useVirtualScrolling.js
import { ref, computed, onMounted, onUnmounted } from 'vue'

export function useVirtualScrolling(items, itemHeight = 50, containerHeight = 400) {
  const scrollTop = ref(0)
  const containerRef = ref(null)
  
  const visibleStart = computed(() => 
    Math.floor(scrollTop.value / itemHeight)
  )
  
  const visibleEnd = computed(() => 
    Math.min(
      visibleStart.value + Math.ceil(containerHeight / itemHeight) + 1,
      items.value.length
    )
  )
  
  const visibleItems = computed(() => 
    items.value.slice(visibleStart.value, visibleEnd.value)
  )
  
  const totalHeight = computed(() => 
    items.value.length * itemHeight
  )
  
  const offsetY = computed(() => 
    visibleStart.value * itemHeight
  )
  
  const handleScroll = (event) => {
    scrollTop.value = event.target.scrollTop
  }
  
  onMounted(() => {
    if (containerRef.value) {
      containerRef.value.addEventListener('scroll', handleScroll)
    }
  })
  
  onUnmounted(() => {
    if (containerRef.value) {
      containerRef.value.removeEventListener('scroll', handleScroll)
    }
  })
  
  return {
    containerRef,
    visibleItems,
    totalHeight,
    offsetY
  }
}
```

#### 2. Testing Setup
```javascript
// vitest.config.js
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js']
  }
})

// src/test/setup.js
import { config } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

const vuetify = createVuetify({
  components,
  directives,
})

config.global.plugins = [vuetify]
```

#### 3. Component Testing Example
```javascript
// src/modules/video-processing/components/__tests__/VideoUpload.spec.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import VideoUpload from '../VideoUpload.vue'

describe('VideoUpload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders upload interface', () => {
    const wrapper = mount(VideoUpload)
    expect(wrapper.find('.drop-zone').exists()).toBe(true)
    expect(wrapper.find('input[type="file"]').exists()).toBe(true)
  })

  it('handles file selection', async () => {
    const wrapper = mount(VideoUpload)
    const fileInput = wrapper.find('input[type="file"]')
    
    const mockFile = new File(['video content'], 'test.mp4', { type: 'video/mp4' })
    const mockEvent = { target: { files: [mockFile] } }
    
    await fileInput.trigger('change', mockEvent)
    
    expect(wrapper.vm.selectedFiles).toHaveLength(1)
    expect(wrapper.vm.selectedFiles[0].name).toBe('test.mp4')
  })

  it('validates file types', async () => {
    const wrapper = mount(VideoUpload)
    
    const mockFile = new File(['text content'], 'test.txt', { type: 'text/plain' })
    const mockEvent = { target: { files: [mockFile] } }
    
    await wrapper.find('input[type="file"]').trigger('change', mockEvent)
    
    expect(wrapper.vm.selectedFiles).toHaveLength(0)
  })
})
```

## Performance Optimization Best Practices

### 1. Memory Management
```javascript
// Prevent memory leaks in video processing
const useVideoProcessor = () => {
  const videoElement = ref(null)
  const canvas = ref(null)
  const context = ref(null)
  
  const cleanup = () => {
    if (videoElement.value) {
      videoElement.value.pause()
      videoElement.value.src = ''
      videoElement.value.load()
    }
    
    if (context.value) {
      context.value.clearRect(0, 0, canvas.value.width, canvas.value.height)
    }
  }
  
  onUnmounted(() => {
    cleanup()
  })
  
  return { videoElement, canvas, context, cleanup }
}
```

### 2. Code Splitting
```javascript
// Lazy load heavy components
const HeavyProcessingComponent = defineAsyncComponent({
  loader: () => import('./HeavyProcessingComponent.vue'),
  loadingComponent: LoadingSpinner,
  errorComponent: ErrorDisplay,
  delay: 200,
  timeout: 3000
})
```

### 3. Bundle Optimization
```javascript
// webpack.config.js - optimization settings
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
        },
        common: {
          minChunks: 2,
          chunks: 'all',
          enforce: true
        }
      }
    }
  }
}
```

## Security Best Practices

### 1. File Upload Security
```javascript
// File validation
const validateFile = (file) => {
  const allowedTypes = ['video/mp4', 'video/avi', 'video/mov']
  const maxSize = 100 * 1024 * 1024 // 100MB
  
  if (!allowedTypes.includes(file.type)) {
    throw new Error('Invalid file type')
  }
  
  if (file.size > maxSize) {
    throw new Error('File too large')
  }
  
  return true
}
```

### 2. API Security
```javascript
// CSRF protection and secure headers
apiClient.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest'
apiClient.defaults.withCredentials = true
```

## Deployment Configuration

### 1. Docker Configuration
```dockerfile
# Dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2. Production Build
```javascript
// Production environment variables
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_WEBSOCKET_URL=wss://api.yourdomain.com
VITE_MAX_FILE_SIZE=104857600
VITE_SUPPORTED_FORMATS=mp4,avi,mov
```

## Migration Checklist

### Pre-Migration
- [ ] Audit current Gradio application features
- [ ] Set up development environment
- [ ] Create project structure
- [ ] Configure build tools and dependencies

### Core Migration
- [ ] Implement state management with Pinia
- [ ] Create file upload components
- [ ] Set up WebSocket communication
- [ ] Implement real-time progress tracking
- [ ] Create video processing pipeline

### Advanced Features
- [ ] Build UMAP visualization component
- [ ] Implement similarity analysis
- [ ] Create analytics dashboard
- [ ] Add settings management
- [ ] Implement user authentication

### Testing & Optimization
- [ ] Write unit tests for all components
- [ ] Implement E2E tests for critical workflows
- [ ] Optimize bundle sizes
- [ ] Implement lazy loading
- [ ] Performance testing and optimization

### Deployment
- [ ] Configure production build
- [ ] Set up CI/CD pipeline
- [ ] Deploy to staging environment
- [ ] Conduct user acceptance testing
- [ ] Deploy to production

This comprehensive guide provides a complete roadmap for migrating your Gradio-based face recognition application to a modern, scalable Vue.js frontend while maintaining all existing functionality and improving performance, user experience, and maintainability.
