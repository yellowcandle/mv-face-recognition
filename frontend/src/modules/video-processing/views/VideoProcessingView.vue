<template>
  <div class="video-processing">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h3 mb-6">Video Processing</h1>
        <p class="text-body-1 text-grey mb-6">
          Process videos for face recognition and generate detailed analysis reports.
        </p>
      </v-col>
    </v-row>

    <!-- Upload Section -->
    <v-row v-if="showUploadSection">
      <v-col cols="12">
        <VideoUpload
          @upload-complete="handleUploadComplete"
          @upload-start="handleUploadStart"
        />
      </v-col>
    </v-row>

    <!-- Main Processing Interface -->
    <v-row class="mt-4">
      <v-col cols="12" lg="5">
        <!-- Video Selection -->
        <VideoSelector
          @video-selected="handleVideoSelected"
          class="mb-4"
        />
        
        <!-- Quick Actions -->
        <v-card>
          <v-card-title>Quick Actions</v-card-title>
          <v-card-text>
            <div class="d-flex flex-column gap-2">
              <v-btn
                variant="outlined"
                prepend-icon="mdi-upload"
                @click="toggleUploadSection"
              >
                {{ showUploadSection ? 'Hide' : 'Show' }} Upload
              </v-btn>
              
              <v-btn
                variant="outlined"
                prepend-icon="mdi-refresh"
                @click="refreshVideos"
              >
                Refresh Videos
              </v-btn>
              
              <v-btn
                variant="outlined"
                prepend-icon="mdi-history"
                @click="viewProcessingHistory"
              >
                Processing History
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="7">
        <!-- Processing Dashboard -->
        <ProcessingDashboard
          @processing-started="handleProcessingStarted"
          @processing-completed="handleProcessingCompleted"
        />
      </v-col>
    </v-row>

    <!-- Processing Jobs History -->
    <v-row v-if="showJobsHistory" class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-history</v-icon>
            Processing History
            <v-spacer></v-spacer>
            <v-btn
              icon="mdi-close"
              variant="text"
              @click="showJobsHistory = false"
            />
          </v-card-title>
          
          <v-card-text>
            <v-data-table
              :items="processingJobs"
              :headers="jobHeaders"
              :loading="loadingJobs"
              class="elevation-1"
            >
              <template v-slot:item.status="{ item }">
                <v-chip
                  :color="getStatusColor(item.status)"
                  size="small"
                  variant="flat"
                >
                  {{ item.status }}
                </v-chip>
              </template>
              
              <template v-slot:item.progress="{ item }">
                <v-progress-linear
                  :value="item.progress"
                  height="8"
                  rounded
                  :color="getStatusColor(item.status)"
                />
              </template>
              
              <template v-slot:item.actions="{ item }">
                <v-btn
                  v-if="item.status === 'completed'"
                  icon="mdi-eye"
                  size="small"
                  variant="text"
                  @click="viewJobResults(item)"
                />
                <v-btn
                  v-if="item.status === 'processing'"
                  icon="mdi-stop"
                  size="small"
                  variant="text"
                  color="error"
                  @click="cancelJob(item)"
                />
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Success/Error Notifications -->
    <v-snackbar
      v-model="showSuccessMessage"
      color="success"
      timeout="4000"
    >
      {{ successMessage }}
      <template v-slot:actions>
        <v-btn @click="showSuccessMessage = false">Close</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVideoProcessingStore } from '../stores/videoProcessing'
import VideoUpload from '../components/VideoUpload.vue'
import VideoSelector from '../components/VideoSelector.vue'
import ProcessingDashboard from '../components/ProcessingDashboard.vue'
import type { VideoInfo, ProcessingJob } from '@/core/types/api'

const router = useRouter()
const videoStore = useVideoProcessingStore()

// UI State
const showUploadSection = ref(false)
const showJobsHistory = ref(false)
const loadingJobs = ref(false)
const showSuccessMessage = ref(false)
const successMessage = ref('')

// Computed
const processingJobs = computed(() => videoStore.processingJobs)

// Job table headers
const jobHeaders = [
  { title: 'Job ID', key: 'job_id', width: '120px' },
  { title: 'Video', key: 'video_id' },
  { title: 'Status', key: 'status', width: '100px' },
  { title: 'Progress', key: 'progress', width: '150px' },
  { title: 'Created', key: 'created_at' },
  { title: 'Actions', key: 'actions', width: '100px', sortable: false }
]

// Methods
const handleUploadStart = (files: File[]) => {
  successMessage.value = `Starting upload of ${files.length} file${files.length !== 1 ? 's' : ''}...`
  showSuccessMessage.value = true
}

const handleUploadComplete = (files: File[]) => {
  successMessage.value = `Successfully uploaded ${files.length} file${files.length !== 1 ? 's' : ''}!`
  showSuccessMessage.value = true
  
  // Hide upload section after successful upload
  setTimeout(() => {
    showUploadSection.value = false
  }, 2000)
}

const handleVideoSelected = (video: VideoInfo) => {
  successMessage.value = `Selected video: ${video.name}`
  showSuccessMessage.value = true
}

const handleProcessingStarted = (jobId: string) => {
  successMessage.value = `Processing started! Job ID: ${jobId.substring(0, 8)}...`
  showSuccessMessage.value = true
}

const handleProcessingCompleted = (result: any) => {
  successMessage.value = `Processing completed! Found ${result.matches_found} face matches.`
  showSuccessMessage.value = true
}

const toggleUploadSection = () => {
  showUploadSection.value = !showUploadSection.value
}

const refreshVideos = async () => {
  await videoStore.loadVideos()
  successMessage.value = 'Videos refreshed!'
  showSuccessMessage.value = true
}

const viewProcessingHistory = async () => {
  showJobsHistory.value = true
  loadingJobs.value = true
  
  try {
    await videoStore.getProcessingJobs()
  } catch (error) {
    console.error('Failed to load processing jobs:', error)
  } finally {
    loadingJobs.value = false
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'success'
    case 'processing': return 'warning'
    case 'failed': return 'error'
    case 'pending': return 'info'
    default: return 'grey'
  }
}

const viewJobResults = (job: ProcessingJob) => {
  router.push({
    name: 'FaceRecognition',
    query: {
      job_id: job.job_id,
      video_id: job.video_id
    }
  })
}

const cancelJob = async (job: ProcessingJob) => {
  try {
    await videoStore.cancelProcessing()
    successMessage.value = `Job ${job.job_id.substring(0, 8)}... cancelled`
    showSuccessMessage.value = true
  } catch (error) {
    console.error('Failed to cancel job:', error)
  }
}

// Load initial data
onMounted(() => {
  videoStore.loadVideos()
})
</script>

<style scoped>
.gap-2 > * {
  margin-bottom: 0.5rem;
}

.gap-2 > *:last-child {
  margin-bottom: 0;
}
</style>