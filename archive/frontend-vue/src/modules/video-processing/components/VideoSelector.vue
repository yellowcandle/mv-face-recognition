<template>
  <v-card class="video-selector">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-video</v-icon>
      Select Video
      <v-spacer></v-spacer>
      <v-btn
        icon="mdi-refresh"
        variant="text"
        @click="refreshVideos"
        :loading="loadingVideos"
      />
    </v-card-title>
    
    <v-card-text>
      <!-- Video List -->
      <div v-if="!loadingVideos && hasVideos">
        <v-list>
          <v-list-item
            v-for="video in videos"
            :key="video.id"
            :class="{ 'v-list-item--active': selectedVideo?.id === video.id }"
            @click="selectVideo(video)"
          >
            <template v-slot:prepend>
              <v-avatar color="primary" variant="tonal">
                <v-icon>mdi-video</v-icon>
              </v-avatar>
            </template>
            
            <v-list-item-title>{{ video.name }}</v-list-item-title>
            <v-list-item-subtitle class="text-wrap">
              <div class="video-details">
                <span>{{ formatDuration(video.duration_seconds) }}</span>
                <span>{{ video.width }}×{{ video.height }}</span>
                <span>{{ formatFileSize(video.size) }}</span>
                <span>{{ Math.round(video.fps) }}fps</span>
              </div>
            </v-list-item-subtitle>
            
            <template v-slot:append>
              <div class="d-flex flex-column align-end">
                <v-chip
                  v-if="selectedVideo?.id === video.id"
                  color="primary"
                  size="small"
                  variant="flat"
                >
                  Selected
                </v-chip>
                
                <v-btn
                  icon="mdi-information"
                  size="small"
                  variant="text"
                  @click.stop="showVideoInfo(video)"
                />
              </div>
            </template>
          </v-list-item>
        </v-list>
      </div>
      
      <!-- Loading State -->
      <div v-else-if="loadingVideos" class="text-center py-8">
        <v-progress-circular
          indeterminate
          size="60"
          color="primary"
        ></v-progress-circular>
        <p class="mt-4 text-body-1">Loading videos...</p>
      </div>
      
      <!-- Empty State -->
      <div v-else class="text-center py-8">
        <v-icon size="80" color="grey-lighten-1">mdi-video-off</v-icon>
        <h3 class="text-h6 mt-4 mb-2">No Videos Found</h3>
        <p class="text-body-2 text-grey mb-4">
          Upload some videos to get started with face recognition processing.
        </p>
        <v-btn
          color="primary"
          prepend-icon="mdi-refresh"
          @click="refreshVideos"
        >
          Refresh
        </v-btn>
      </div>
      
      <!-- Selected Video Info -->
      <v-card v-if="selectedVideo" variant="tonal" color="primary" class="mt-4">
        <v-card-text>
          <div class="d-flex align-center">
            <v-icon class="mr-2">mdi-check-circle</v-icon>
            <div>
              <div class="font-weight-medium">Selected: {{ selectedVideo.name }}</div>
              <div class="text-caption">
                Ready for processing • {{ selectedVideo.frame_count.toLocaleString() }} frames
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </v-card-text>
    
    <!-- Video Info Dialog -->
    <v-dialog v-model="showInfoDialog" max-width="600">
      <v-card v-if="infoVideo">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-information</v-icon>
          Video Information
        </v-card-title>
        
        <v-card-text>
          <v-table density="compact">
            <tbody>
              <tr>
                <td class="font-weight-medium">Name</td>
                <td>{{ infoVideo.name }}</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Filename</td>
                <td>{{ infoVideo.filename }}</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Duration</td>
                <td>{{ formatDuration(infoVideo.duration_seconds) }}</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Resolution</td>
                <td>{{ infoVideo.width }}×{{ infoVideo.height }}</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Frame Rate</td>
                <td>{{ infoVideo.fps.toFixed(2) }} fps</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Total Frames</td>
                <td>{{ infoVideo.frame_count.toLocaleString() }}</td>
              </tr>
              <tr>
                <td class="font-weight-medium">File Size</td>
                <td>{{ formatFileSize(infoVideo.size) }}</td>
              </tr>
              <tr v-if="infoVideo.created_at">
                <td class="font-weight-medium">Created</td>
                <td>{{ formatDate(infoVideo.created_at) }}</td>
              </tr>
            </tbody>
          </v-table>
          
          <!-- Processing Estimation -->
          <v-divider class="my-4"></v-divider>
          
          <div class="text-subtitle-2 mb-2">Processing Estimation</div>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title>Frames to Process (skip=5)</v-list-item-title>
              <v-list-item-subtitle>
                ~{{ Math.ceil(infoVideo.frame_count / 5).toLocaleString() }} frames
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Estimated Time</v-list-item-title>
              <v-list-item-subtitle>
                ~{{ estimateProcessingTime(infoVideo) }}
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            v-if="selectedVideo?.id !== infoVideo.id"
            color="primary"
            @click="selectVideoFromInfo"
          >
            Select This Video
          </v-btn>
          <v-btn @click="showInfoDialog = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useVideoProcessingStore } from '../stores/videoProcessing'
import type { VideoInfo } from '@/core/types/api'

const emit = defineEmits<{
  'video-selected': [video: VideoInfo]
}>()

const videoStore = useVideoProcessingStore()

// State
const showInfoDialog = ref(false)
const infoVideo = ref<VideoInfo | null>(null)

// Computed
const videos = computed(() => videoStore.videos)
const selectedVideo = computed(() => videoStore.selectedVideo)
const loadingVideos = computed(() => videoStore.loadingVideos)
const hasVideos = computed(() => videoStore.hasVideos)

// Methods
const refreshVideos = async () => {
  await videoStore.loadVideos()
}

const selectVideo = (video: VideoInfo) => {
  videoStore.selectVideo(video)
  emit('video-selected', video)
}

const showVideoInfo = (video: VideoInfo) => {
  infoVideo.value = video
  showInfoDialog.value = true
}

const selectVideoFromInfo = () => {
  if (infoVideo.value) {
    selectVideo(infoVideo.value)
    showInfoDialog.value = false
  }
}

const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  } else {
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleString()
}

const estimateProcessingTime = (video: VideoInfo): string => {
  // Rough estimation: ~30 frames per second processing speed
  const framesToProcess = Math.ceil(video.frame_count / 5)
  const estimatedSeconds = framesToProcess / 30
  
  if (estimatedSeconds < 60) {
    return `${Math.ceil(estimatedSeconds)} seconds`
  } else if (estimatedSeconds < 3600) {
    return `${Math.ceil(estimatedSeconds / 60)} minutes`
  } else {
    return `${Math.ceil(estimatedSeconds / 3600)} hours`
  }
}

// Load videos on mount
onMounted(() => {
  refreshVideos()
})
</script>

<style scoped>
.video-details {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.video-details span {
  background: rgba(var(--v-theme-primary), 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.v-list-item--active {
  background: rgba(var(--v-theme-primary), 0.08);
  border-left: 3px solid rgb(var(--v-theme-primary));
}
</style>