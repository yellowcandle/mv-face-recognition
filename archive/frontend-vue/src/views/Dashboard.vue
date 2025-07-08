<template>
  <div class="dashboard">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h3 mb-6">Dashboard</h1>
      </v-col>
    </v-row>

    <!-- System Status Cards -->
    <v-row>
      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="d-flex align-center">
              <v-icon size="40" color="primary" class="mr-4">mdi-database</v-icon>
              <div>
                <div class="text-h6">Contestants</div>
                <div class="text-h4">{{ contestantCount }}</div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="d-flex align-center">
              <v-icon size="40" color="success" class="mr-4">mdi-video</v-icon>
              <div>
                <div class="text-h6">Videos</div>
                <div class="text-h4">{{ videoCount }}</div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="d-flex align-center">
              <v-icon size="40" color="warning" class="mr-4">mdi-cog</v-icon>
              <div>
                <div class="text-h6">Processing</div>
                <div class="text-h4">{{ processingJobs }}</div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="d-flex align-center">
              <v-icon size="40" color="info" class="mr-4">mdi-chart-line</v-icon>
              <div>
                <div class="text-h6">Results</div>
                <div class="text-h4">{{ resultsCount }}</div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Recent Activity -->
    <v-row class="mt-6">
      <v-col cols="12" md="8">
        <v-card>
          <v-card-title>Recent Processing Activity</v-card-title>
          <v-card-text>
            <v-list v-if="recentActivity.length > 0">
              <v-list-item
                v-for="activity in recentActivity"
                :key="activity.id"
              >
                <template v-slot:prepend>
                  <v-icon :color="getStatusColor(activity.status)">
                    {{ getStatusIcon(activity.status) }}
                  </v-icon>
                </template>
                <v-list-item-title>{{ activity.videoName }}</v-list-item-title>
                <v-list-item-subtitle>
                  {{ activity.status }} • {{ formatTime(activity.timestamp) }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
            <div v-else class="text-center py-8 text-grey">
              No recent activity
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card>
          <v-card-title>System Status</v-card-title>
          <v-card-text>
            <div class="d-flex align-center mb-3">
              <v-icon color="success" class="mr-2">mdi-check-circle</v-icon>
              <span>ChromaDB Connected</span>
            </div>
            <div class="d-flex align-center mb-3">
              <v-icon color="success" class="mr-2">mdi-check-circle</v-icon>
              <span>Face Detection Model Loaded</span>
            </div>
            <div class="d-flex align-center">
              <v-icon color="success" class="mr-2">mdi-check-circle</v-icon>
              <span>All Services Running</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quick Actions -->
    <v-row class="mt-6">
      <v-col cols="12">
        <v-card>
          <v-card-title>Quick Actions</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" sm="6" md="3">
                <v-btn
                  block
                  size="large"
                  color="primary"
                  prepend-icon="mdi-video-plus"
                  to="/video-processing"
                >
                  Process Video
                </v-btn>
              </v-col>
              <v-col cols="12" sm="6" md="3">
                <v-btn
                  block
                  size="large"
                  color="secondary"
                  prepend-icon="mdi-face-recognition"
                  to="/face-recognition"
                >
                  View Results
                </v-btn>
              </v-col>
              <v-col cols="12" sm="6" md="3">
                <v-btn
                  block
                  size="large"
                  color="success"
                  prepend-icon="mdi-chart-line"
                  to="/analytics"
                >
                  Analytics
                </v-btn>
              </v-col>
              <v-col cols="12" sm="6" md="3">
                <v-btn
                  block
                  size="large"
                  color="warning"
                  prepend-icon="mdi-cog"
                  to="/settings"
                >
                  Settings
                </v-btn>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMainStore } from '@/stores/main'
import { useContestantsStore } from '@/stores/contestants'
import { useVideoProcessingStore } from '@/modules/video-processing/stores/videoProcessing'

const mainStore = useMainStore()
const contestantsStore = useContestantsStore()
const videoStore = useVideoProcessingStore()

// Reactive data from stores
const contestantCount = computed(() => mainStore.dashboardStats.contestants)
const videoCount = computed(() => mainStore.dashboardStats.videos)
const processingJobs = computed(() => mainStore.dashboardStats.processingJobs)
const resultsCount = computed(() => {
  // Count completed jobs with results
  return videoStore.processingJobs.filter(job => job.status === 'completed').length
})

// Recent activity from processing jobs
const recentActivity = computed(() => {
  return videoStore.processingJobs
    .slice(0, 5) // Latest 5 jobs
    .map(job => ({
      id: job.job_id,
      videoName: `Video ${job.video_id}`,
      status: job.status,
      timestamp: job.created_at
    }))
})

// Loading states
const isLoading = computed(() => mainStore.isLoading)
const systemStatus = computed(() => mainStore.systemStatus)
const apiConnected = computed(() => mainStore.apiConnected)

// Auto-refresh interval
let refreshInterval: number | null = null

// Methods
const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'success'
    case 'processing': return 'warning'
    case 'failed': return 'error'
    default: return 'info'
  }
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed': return 'mdi-check-circle'
    case 'processing': return 'mdi-loading'
    case 'failed': return 'mdi-alert-circle'
    default: return 'mdi-information'
  }
}

const formatTime = (timestamp: string) => {
  return new Date(timestamp).toLocaleString()
}

const refreshDashboard = async () => {
  try {
    await Promise.all([
      mainStore.fetchSystemStatus(),
      contestantsStore.loadContestants(),
      videoStore.loadVideos(),
      videoStore.getProcessingJobs()
    ])
  } catch (error) {
    console.error('Failed to refresh dashboard:', error)
  }
}

onMounted(async () => {
  // Initialize app and load data
  await mainStore.initializeApp()
  await refreshDashboard()
  
  // Set up auto-refresh every 30 seconds
  refreshInterval = setInterval(refreshDashboard, 30000)
  
  // Start health checks
  const stopHealthChecks = mainStore.startHealthChecks()
  
  // Cleanup on unmount
  onUnmounted(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
    }
    stopHealthChecks()
  })
})
</script>