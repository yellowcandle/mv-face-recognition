<template>
  <v-card class="processing-dashboard">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-cog</v-icon>
      Processing Dashboard
      <v-spacer></v-spacer>
      
      <!-- Connection Status -->
      <v-chip
        :color="isWebSocketConnected ? 'success' : 'error'"
        size="small"
        variant="flat"
      >
        <v-icon start>
          {{ isWebSocketConnected ? 'mdi-wifi' : 'mdi-wifi-off' }}
        </v-icon>
        {{ isWebSocketConnected ? 'Connected' : 'Disconnected' }}
      </v-chip>
    </v-card-title>
    
    <v-card-text>
      <!-- Processing Configuration -->
      <div v-if="!isProcessing && !processingResult" class="processing-config">
        <h3 class="text-h6 mb-4">Processing Configuration</h3>
        
        <v-form ref="configForm" v-model="configValid">
          <v-row>
            <v-col cols="12" md="4">
              <v-slider
                v-model="config.frame_skip"
                label="Frame Skip"
                min="1"
                max="30"
                step="1"
                thumb-label="always"
                color="primary"
              >
                <template v-slot:append>
                  <v-text-field
                    v-model="config.frame_skip"
                    type="number"
                    style="width: 60px"
                    density="compact"
                    hide-details
                    variant="outlined"
                  />
                </template>
              </v-slider>
              <div class="text-caption text-grey">
                Process every {{ config.frame_skip }} frame{{ config.frame_skip !== 1 ? 's' : '' }}
              </div>
            </v-col>
            
            <v-col cols="12" md="4">
              <v-slider
                v-model="config.detection_threshold"
                label="Detection Threshold"
                min="0.1"
                max="1.0"
                step="0.05"
                thumb-label="always"
                color="primary"
              >
                <template v-slot:append>
                  <v-text-field
                    v-model="config.detection_threshold"
                    type="number"
                    style="width: 60px"
                    density="compact"
                    hide-details
                    variant="outlined"
                  />
                </template>
              </v-slider>
              <div class="text-caption text-grey">
                Minimum confidence for face detection
              </div>
            </v-col>
            
            <v-col cols="12" md="4">
              <v-slider
                v-model="config.similarity_threshold"
                label="Similarity Threshold"
                min="0.1"
                max="1.0"
                step="0.05"
                thumb-label="always"
                color="primary"
              >
                <template v-slot:append>
                  <v-text-field
                    v-model="config.similarity_threshold"
                    type="number"
                    style="width: 60px"
                    density="compact"
                    hide-details
                    variant="outlined"
                  />
                </template>
              </v-slider>
              <div class="text-caption text-grey">
                Minimum similarity for face matching
              </div>
            </v-col>
          </v-row>
          
          <v-row class="mt-2">
            <v-col cols="12" md="6">
              <v-text-field
                v-model.number="config.start_time"
                label="Start Time (seconds)"
                type="number"
                min="0"
                variant="outlined"
                density="compact"
                suffix="sec"
              />
            </v-col>
            
            <v-col cols="12" md="6">
              <v-text-field
                v-model.number="config.end_time"
                label="End Time (seconds)"
                type="number"
                min="0"
                variant="outlined"
                density="compact"
                suffix="sec"
                hint="Leave 0 for full video"
                persistent-hint
              />
            </v-col>
          </v-row>
          
          <v-row class="mt-2">
            <v-col cols="12">
              <v-checkbox
                v-model="config.generate_annotated_video"
                label="Generate annotated video with face boxes and names"
                color="primary"
              />
              <v-checkbox
                v-model="config.export_csv"
                label="Export detailed results to CSV"
                color="primary"
              />
            </v-col>
          </v-row>
        </v-form>
        
        <!-- Start Processing Button -->
        <div class="d-flex justify-end mt-4">
          <v-btn
            color="primary"
            size="large"
            prepend-icon="mdi-play"
            :disabled="!canStartProcessing"
            @click="startProcessing"
          >
            Start Processing
          </v-btn>
        </div>
      </div>
      
      <!-- Processing Progress -->
      <div v-else-if="isProcessing" class="processing-progress">
        <div class="text-center mb-6">
          <v-progress-circular
            :value="progressPercent"
            size="120"
            width="8"
            color="primary"
            class="mb-4"
          >
            <div class="text-center">
              <div class="text-h5 font-weight-bold">{{ Math.round(progressPercent) }}%</div>
              <div class="text-caption">Complete</div>
            </div>
          </v-progress-circular>
          
          <h3 class="text-h6">Processing Video...</h3>
          <p class="text-body-2 text-grey">{{ selectedVideo?.name }}</p>
        </div>
        
        <!-- Detailed Progress -->
        <v-card variant="tonal" color="primary" class="mb-4">
          <v-card-text>
            <v-row>
              <v-col cols="6" sm="3">
                <div class="text-center">
                  <div class="text-h6 text-primary">{{ currentFrame.toLocaleString() }}</div>
                  <div class="text-caption">Current Frame</div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="text-center">
                  <div class="text-h6 text-primary">{{ totalFrames.toLocaleString() }}</div>
                  <div class="text-caption">Total Frames</div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="text-center">
                  <div class="text-h6 text-success">{{ facesDetected.toLocaleString() }}</div>
                  <div class="text-caption">Faces Detected</div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="text-center">
                  <div class="text-h6 text-warning">{{ matchesFound.toLocaleString() }}</div>
                  <div class="text-caption">Matches Found</div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
        
        <!-- Real-time Stats -->
        <v-row v-if="processingProgress">
          <v-col cols="12" md="6">
            <v-card variant="outlined">
              <v-card-text>
                <div class="d-flex align-center">
                  <v-icon color="info" class="mr-2">mdi-clock</v-icon>
                  <div>
                    <div class="font-weight-medium">Current Frame Time</div>
                    <div class="text-caption">{{ formatTimestamp(processingProgress.frame_timestamp) }}</div>
                  </div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
          
          <v-col cols="12" md="6">
            <v-card variant="outlined">
              <v-card-text>
                <div class="d-flex align-center">
                  <v-icon color="success" class="mr-2">mdi-speedometer</v-icon>
                  <div>
                    <div class="font-weight-medium">Processing Speed</div>
                    <div class="text-caption">{{ processingProgress.processing_fps.toFixed(1) }} fps</div>
                  </div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
        
        <!-- Current Frame Info -->
        <v-alert
          v-if="processingProgress"
          type="info"
          variant="tonal"
          class="mt-4"
        >
          <div class="d-flex justify-between">
            <span>Current frame: {{ processingProgress.current_frame_faces }} faces detected</span>
            <span>{{ processingProgress.current_frame_recognized }} recognized</span>
          </div>
        </v-alert>
        
        <!-- Cancel Button -->
        <div class="d-flex justify-center mt-6">
          <v-btn
            color="error"
            variant="outlined"
            prepend-icon="mdi-stop"
            @click="cancelProcessing"
          >
            Cancel Processing
          </v-btn>
        </div>
      </div>
      
      <!-- Processing Results -->
      <div v-else-if="processingResult" class="processing-results">
        <div class="text-center mb-6">
          <v-icon size="80" color="success">mdi-check-circle</v-icon>
          <h3 class="text-h5 mt-4">Processing Complete!</h3>
          <p class="text-body-1 text-grey">{{ selectedVideo?.name }}</p>
        </div>
        
        <!-- Results Summary -->
        <v-row>
          <v-col cols="6" md="3">
            <v-card variant="tonal" color="primary">
              <v-card-text class="text-center">
                <div class="text-h4 text-primary">{{ processingResult.total_frames.toLocaleString() }}</div>
                <div class="text-caption">Frames Processed</div>
              </v-card-text>
            </v-card>
          </v-col>
          
          <v-col cols="6" md="3">
            <v-card variant="tonal" color="success">
              <v-card-text class="text-center">
                <div class="text-h4 text-success">{{ processingResult.faces_detected.toLocaleString() }}</div>
                <div class="text-caption">Faces Detected</div>
              </v-card-text>
            </v-card>
          </v-col>
          
          <v-col cols="6" md="3">
            <v-card variant="tonal" color="warning">
              <v-card-text class="text-center">
                <div class="text-h4 text-warning">{{ processingResult.matches_found.toLocaleString() }}</div>
                <div class="text-caption">Matches Found</div>
              </v-card-text>
            </v-card>
          </v-col>
          
          <v-col cols="6" md="3">
            <v-card variant="tonal" color="info">
              <v-card-text class="text-center">
                <div class="text-h4 text-info">{{ processingResult.unique_contestants }}</div>
                <div class="text-caption">Unique Contestants</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
        
        <!-- Processing Time -->
        <v-alert type="success" variant="tonal" class="mt-4">
          <div class="d-flex justify-between align-center">
            <span>Processing completed successfully</span>
            <span class="font-weight-medium">
              {{ formatProcessingTime(processingResult.processing_time) }}
            </span>
          </div>
        </v-alert>
        
        <!-- Action Buttons -->
        <div class="d-flex flex-wrap gap-3 justify-center mt-6">
          <v-btn
            color="primary"
            prepend-icon="mdi-eye"
            @click="viewResults"
          >
            View Detailed Results
          </v-btn>
          
          <v-btn
            v-if="processingResult.annotated_video_path"
            color="secondary"
            prepend-icon="mdi-download"
            @click="downloadAnnotatedVideo"
          >
            Download Video
          </v-btn>
          
          <v-btn
            v-if="processingResult.csv_path"
            color="success"
            prepend-icon="mdi-file-table"
            @click="downloadCsv"
          >
            Download CSV
          </v-btn>
          
          <v-btn
            color="info"
            prepend-icon="mdi-refresh"
            variant="outlined"
            @click="startNewProcessing"
          >
            Process Another Video
          </v-btn>
        </div>
      </div>
      
      <!-- Error Display -->
      <v-alert
        v-if="error"
        type="error"
        variant="tonal"
        closable
        class="mt-4"
        @click:close="clearError"
      >
        {{ error }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVideoProcessingStore } from '../stores/videoProcessing'
import { useWebSocket } from '@/core/composables/useWebSocket'
import type { ProcessingConfig } from '@/core/types/api'

const emit = defineEmits<{
  'processing-started': [jobId: string]
  'processing-completed': [result: any]
}>()

const router = useRouter()
const videoStore = useVideoProcessingStore()
const websocket = useWebSocket()

// Form validation
const configForm = ref()
const configValid = ref(true)

// Configuration state
const config = ref<ProcessingConfig>({
  frame_skip: 5,
  detection_threshold: 0.5,
  similarity_threshold: 0.6,
  start_time: 0,
  end_time: 0,
  generate_annotated_video: true,
  export_csv: true
})

// Computed properties
const selectedVideo = computed(() => videoStore.selectedVideo)
const isProcessing = computed(() => videoStore.isProcessing)
const currentJob = computed(() => videoStore.currentJob)
const processingProgress = computed(() => videoStore.processingProgress)
const processingResult = computed(() => videoStore.processingResult)
const error = computed(() => videoStore.error)
const isWebSocketConnected = computed(() => websocket.isConnected.value)

const canStartProcessing = computed(() => 
  selectedVideo.value && !isProcessing.value && configValid.value
)

const progressPercent = computed(() => 
  processingProgress.value?.progress || 0
)

const currentFrame = computed(() => 
  processingProgress.value?.current_frame || 0
)

const totalFrames = computed(() => 
  processingProgress.value?.total_frames || 0
)

const facesDetected = computed(() => 
  processingProgress.value?.faces_detected || 0
)

const matchesFound = computed(() => 
  processingProgress.value?.matches_found || 0
)

// Methods
const startProcessing = async () => {
  if (!selectedVideo.value || !configValid.value) return
  
  try {
    const job = await videoStore.startProcessing(config.value)
    
    // Subscribe to WebSocket updates for this job
    websocket.subscribeToJob(job.job_id)
    
    emit('processing-started', job.job_id)
    
  } catch (err) {
    console.error('Failed to start processing:', err)
  }
}

const cancelProcessing = async () => {
  await videoStore.cancelProcessing()
  
  if (currentJob.value) {
    websocket.unsubscribeFromJob(currentJob.value.job_id)
  }
}

const viewResults = () => {
  if (processingResult.value) {
    router.push({
      name: 'FaceRecognition',
      query: { 
        job_id: processingResult.value.job_id,
        video_id: processingResult.value.video_id
      }
    })
  }
}

const downloadAnnotatedVideo = () => {
  if (processingResult.value) {
    videoStore.downloadAnnotatedVideo(processingResult.value.job_id)
  }
}

const downloadCsv = () => {
  if (processingResult.value) {
    videoStore.downloadCsvResults(processingResult.value.job_id)
  }
}

const startNewProcessing = () => {
  videoStore.resetProcessing()
}

const clearError = () => {
  videoStore.clearError()
}

const formatTimestamp = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  } else {
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }
}

const formatProcessingTime = (seconds: number): string => {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`
  } else if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`
  } else {
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  }
}

// WebSocket event handlers
const setupWebSocketHandlers = () => {
  // Processing progress updates
  const unsubscribeProgress = websocket.on('processing_progress', (data) => {
    videoStore.updateProcessingProgress(data)
  })
  
  // Processing completion
  const unsubscribeComplete = websocket.on('processing_complete', (data) => {
    videoStore.completeProcessing(data)
    emit('processing-completed', data)
    
    if (currentJob.value) {
      websocket.unsubscribeFromJob(currentJob.value.job_id)
    }
  })
  
  // Processing errors
  const unsubscribeError = websocket.on('processing_error', (data) => {
    videoStore.failProcessing(data.job_id, data.error)
    
    if (currentJob.value) {
      websocket.unsubscribeFromJob(currentJob.value.job_id)
    }
  })
  
  // Store unsubscribe functions for cleanup
  return [unsubscribeProgress, unsubscribeComplete, unsubscribeError]
}

// Lifecycle
let websocketUnsubscribers: (() => void)[] = []

onMounted(() => {
  websocketUnsubscribers = setupWebSocketHandlers()
})

onUnmounted(() => {
  // Clean up WebSocket subscriptions
  websocketUnsubscribers.forEach(unsubscribe => unsubscribe())
  
  if (currentJob.value) {
    websocket.unsubscribeFromJob(currentJob.value.job_id)
  }
})
</script>

<style scoped>
.processing-dashboard {
  min-height: 400px;
}

.processing-config,
.processing-progress,
.processing-results {
  min-height: 300px;
}

.text-h4 {
  font-weight: 600;
}

.gap-3 > * {
  margin: 0.375rem;
}
</style>