<template>
  <div class="face-recognition">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h3 mb-6">Face Recognition</h1>
        <p class="text-body-1 text-grey mb-6">
          Explore contestants and view detailed recognition results from video processing.
        </p>
      </v-col>
    </v-row>

    <!-- Main Content -->
    <v-row>
      <v-col cols="12" lg="8">
        <!-- Contestant Gallery -->
        <ContestantGallery
          @contestant-selected="handleContestantSelected"
        />
      </v-col>
      
      <v-col cols="12" lg="4">
        <!-- Recognition Results Panel -->
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-chart-box-outline</v-icon>
            Recognition Results
          </v-card-title>
          
          <v-card-text>
            <div v-if="!selectedJobId" class="text-center py-8">
              <v-icon size="60" color="grey-lighten-1">mdi-file-search</v-icon>
              <h3 class="text-h6 mt-4 mb-2">No Results Selected</h3>
              <p class="text-body-2 text-grey mb-4">
                Process a video to see recognition results here.
              </p>
              <v-btn
                color="primary"
                prepend-icon="mdi-video"
                to="/video-processing"
              >
                Process Video
              </v-btn>
            </div>
            
            <!-- Results will be shown here when job is selected -->
            <div v-else class="results-content">
              <v-alert type="info" variant="tonal" class="mb-4">
                Showing results for job: {{ selectedJobId.substring(0, 8) }}...
              </v-alert>
              
              <!-- Placeholder for actual results -->
              <div class="text-center py-4">
                <v-progress-circular indeterminate color="primary" />
                <p class="mt-2">Loading recognition results...</p>
              </div>
            </div>
          </v-card-text>
        </v-card>
        
        <!-- Quick Stats -->
        <v-card class="mt-4">
          <v-card-title>Quick Stats</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="6">
                <div class="text-center">
                  <div class="text-h4 text-primary">{{ contestantCount }}</div>
                  <div class="text-caption">Total Contestants</div>
                </div>
              </v-col>
              <v-col cols="6">
                <div class="text-center">
                  <div class="text-h4 text-success">{{ embeddingCoverage.toFixed(1) }}%</div>
                  <div class="text-caption">Ready for Recognition</div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
        
        <!-- Selected Contestant Info -->
        <v-card v-if="selectedContestant" class="mt-4">
          <v-card-title>Selected Contestant</v-card-title>
          <v-card-text>
            <div class="d-flex align-center">
              <v-avatar size="60" class="mr-4">
                <v-img
                  v-if="selectedContestant.photos.length > 0"
                  :src="getPhotoUrl(selectedContestant.photos[0])"
                />
                <v-icon v-else>mdi-account</v-icon>
              </v-avatar>
              
              <div>
                <h3 class="text-h6">{{ selectedContestant.name }}</h3>
                <p class="text-body-2 text-grey mb-1">ID: {{ selectedContestant.id }}</p>
                <v-chip
                  :color="selectedContestant.embedding_available ? 'success' : 'warning'"
                  size="small"
                  variant="flat"
                >
                  {{ selectedContestant.embedding_available ? 'Ready' : 'No Embedding' }}
                </v-chip>
              </div>
            </div>
            
            <div class="mt-4">
              <v-btn
                color="primary"
                variant="outlined"
                block
                prepend-icon="mdi-magnify"
                @click="searchForContestant"
              >
                Search in Results
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useContestantsStore } from '@/stores/contestants'
import ContestantGallery from '../components/ContestantGallery.vue'
import type { Contestant } from '@/core/types/api'

const route = useRoute()
const contestantsStore = useContestantsStore()

// State
const selectedJobId = ref<string | null>(null)

// Computed
const selectedContestant = computed(() => contestantsStore.selectedContestant)
const contestantCount = computed(() => contestantsStore.contestantCount)
const embeddingCoverage = computed(() => contestantsStore.embeddingCoverage)

// Methods
const handleContestantSelected = (contestant: Contestant) => {
  console.log('Selected contestant:', contestant.name)
}

const searchForContestant = () => {
  if (selectedContestant.value && selectedJobId.value) {
    // Implement search functionality for specific contestant in results
    console.log('Searching for', selectedContestant.value.name, 'in job', selectedJobId.value)
  }
}

const getPhotoUrl = (photoPath: string) => {
  return `/api/contestants/photos/${photoPath}`
}

// Check for job_id in route query
onMounted(() => {
  if (route.query.job_id) {
    selectedJobId.value = route.query.job_id as string
  }
})
</script>

<style scoped>
.results-content {
  min-height: 200px;
}
</style>