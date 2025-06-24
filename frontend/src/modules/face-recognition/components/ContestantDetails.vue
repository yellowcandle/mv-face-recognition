<template>
  <v-card class="contestant-details">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-account-details</v-icon>
      Contestant Details
      <v-spacer></v-spacer>
      <v-btn
        icon="mdi-close"
        variant="text"
        @click="$emit('close')"
      />
    </v-card-title>
    
    <v-card-text>
      <v-row>
        <!-- Basic Information -->
        <v-col cols="12" md="4">
          <v-card variant="outlined">
            <v-card-title class="text-h6">Basic Information</v-card-title>
            <v-card-text>
              <v-list density="compact">
                <v-list-item>
                  <v-list-item-title>Name</v-list-item-title>
                  <v-list-item-subtitle>{{ contestant.name }}</v-list-item-subtitle>
                </v-list-item>
                
                <v-list-item>
                  <v-list-item-title>ID</v-list-item-title>
                  <v-list-item-subtitle>{{ contestant.id }}</v-list-item-subtitle>
                </v-list-item>
                
                <v-list-item>
                  <v-list-item-title>Photos</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ contestant.photos.length }} photo{{ contestant.photos.length !== 1 ? 's' : '' }}
                  </v-list-item-subtitle>
                </v-list-item>
                
                <v-list-item>
                  <v-list-item-title>Embedding Status</v-list-item-title>
                  <v-list-item-subtitle>
                    <v-chip
                      :color="contestant.embedding_available ? 'success' : 'warning'"
                      size="small"
                      variant="flat"
                    >
                      <v-icon start size="16">
                        {{ contestant.embedding_available ? 'mdi-check' : 'mdi-alert' }}
                      </v-icon>
                      {{ contestant.embedding_available ? 'Available' : 'Not Available' }}
                    </v-chip>
                  </v-list-item-subtitle>
                </v-list-item>
                
                <v-list-item v-if="contestant.created_at">
                  <v-list-item-title>Created</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ formatDate(contestant.created_at) }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>
        
        <!-- Photo Gallery -->
        <v-col cols="12" md="8">
          <v-card variant="outlined">
            <v-card-title class="d-flex align-center">
              <span class="text-h6">Photo Gallery</span>
              <v-spacer></v-spacer>
              <v-btn-toggle
                v-model="photoViewMode"
                mandatory
                variant="outlined"
                density="compact"
              >
                <v-btn value="grid" size="small">
                  <v-icon>mdi-view-grid</v-icon>
                </v-btn>
                <v-btn value="carousel" size="small">
                  <v-icon>mdi-view-carousel</v-icon>
                </v-btn>
              </v-btn-toggle>
            </v-card-title>
            
            <v-card-text>
              <!-- Grid View -->
              <div v-if="photoViewMode === 'grid'" class="photo-grid">
                <v-row v-if="contestant.photos.length > 0">
                  <v-col
                    v-for="(photo, index) in contestant.photos"
                    :key="index"
                    cols="6"
                    sm="4"
                    md="3"
                  >
                    <v-card
                      class="photo-card"
                      @click="openPhotoDialog(photo, index)"
                    >
                      <v-img
                        :src="getPhotoUrl(photo)"
                        :alt="`${contestant.name} photo ${index + 1}`"
                        aspect-ratio="1"
                        cover
                      >
                        <template v-slot:placeholder>
                          <div class="d-flex align-center justify-center fill-height">
                            <v-progress-circular indeterminate color="primary" />
                          </div>
                        </template>
                        
                        <template v-slot:error>
                          <div class="d-flex align-center justify-center fill-height bg-grey-lighten-3">
                            <v-icon color="grey">mdi-image-broken</v-icon>
                          </div>
                        </template>
                      </v-img>
                      
                      <v-overlay
                        contained
                        scrim="black"
                        opacity="0"
                        class="photo-overlay"
                      >
                        <v-icon size="30" color="white">mdi-magnify-plus</v-icon>
                      </v-overlay>
                    </v-card>
                  </v-col>
                </v-row>
                
                <div v-else class="text-center py-8">
                  <v-icon size="80" color="grey-lighten-1">mdi-image-off</v-icon>
                  <p class="text-body-2 text-grey mt-2">No photos available</p>
                </div>
              </div>
              
              <!-- Carousel View -->
              <div v-else-if="photoViewMode === 'carousel'" class="photo-carousel">
                <v-carousel
                  v-if="contestant.photos.length > 0"
                  height="300"
                  hide-delimiter-background
                  show-arrows="hover"
                >
                  <v-carousel-item
                    v-for="(photo, index) in contestant.photos"
                    :key="index"
                  >
                    <v-img
                      :src="getPhotoUrl(photo)"
                      :alt="`${contestant.name} photo ${index + 1}`"
                      height="300"
                      cover
                      @click="openPhotoDialog(photo, index)"
                    />
                  </v-carousel-item>
                </v-carousel>
                
                <div v-else class="text-center py-8">
                  <v-icon size="80" color="grey-lighten-1">mdi-image-off</v-icon>
                  <p class="text-body-2 text-grey mt-2">No photos available</p>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
      
      <!-- Recognition Statistics (if available) -->
      <v-row v-if="showStats" class="mt-4">
        <v-col cols="12">
          <v-card variant="outlined">
            <v-card-title class="text-h6">Recognition Statistics</v-card-title>
            <v-card-text>
              <div class="text-center text-grey">
                <v-icon size="60">mdi-chart-line</v-icon>
                <p class="mt-2">Statistics will be available after processing videos</p>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
    
    <v-card-actions>
      <v-spacer></v-spacer>
      <v-btn
        color="primary"
        @click="$emit('select', contestant)"
      >
        Select This Contestant
      </v-btn>
      <v-btn @click="$emit('close')">Close</v-btn>
    </v-card-actions>
  </v-card>
  
  <!-- Photo Dialog -->
  <v-dialog v-model="showPhotoDialog" max-width="800">
    <v-card v-if="selectedPhoto">
      <v-card-title class="d-flex align-center">
        <span>{{ contestant.name }} - Photo {{ selectedPhotoIndex + 1 }}</span>
        <v-spacer></v-spacer>
        <v-btn
          icon="mdi-close"
          variant="text"
          @click="showPhotoDialog = false"
        />
      </v-card-title>
      
      <v-card-text class="pa-0">
        <v-img
          :src="getPhotoUrl(selectedPhoto)"
          :alt="`${contestant.name} photo ${selectedPhotoIndex + 1}`"
          max-height="600"
          contain
        />
      </v-card-text>
      
      <v-card-actions v-if="contestant.photos.length > 1">
        <v-btn
          :disabled="selectedPhotoIndex === 0"
          @click="previousPhoto"
        >
          <v-icon start>mdi-chevron-left</v-icon>
          Previous
        </v-btn>
        
        <v-spacer></v-spacer>
        
        <span class="text-body-2">
          {{ selectedPhotoIndex + 1 }} of {{ contestant.photos.length }}
        </span>
        
        <v-spacer></v-spacer>
        
        <v-btn
          :disabled="selectedPhotoIndex === contestant.photos.length - 1"
          @click="nextPhoto"
        >
          Next
          <v-icon end>mdi-chevron-right</v-icon>
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Contestant } from '@/core/types/api'

interface Props {
  contestant: Contestant
  showStats?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showStats: false
})

const emit = defineEmits<{
  'close': []
  'select': [contestant: Contestant]
}>()

// Local state
const photoViewMode = ref('grid')
const showPhotoDialog = ref(false)
const selectedPhoto = ref<string | null>(null)
const selectedPhotoIndex = ref(0)

// Methods
const getPhotoUrl = (photoPath: string) => {
  return `/api/contestants/photos/${photoPath}`
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

const openPhotoDialog = (photo: string, index: number) => {
  selectedPhoto.value = photo
  selectedPhotoIndex.value = index
  showPhotoDialog.value = true
}

const previousPhoto = () => {
  if (selectedPhotoIndex.value > 0) {
    selectedPhotoIndex.value--
    selectedPhoto.value = props.contestant.photos[selectedPhotoIndex.value]
  }
}

const nextPhoto = () => {
  if (selectedPhotoIndex.value < props.contestant.photos.length - 1) {
    selectedPhotoIndex.value++
    selectedPhoto.value = props.contestant.photos[selectedPhotoIndex.value]
  }
}
</script>

<style scoped>
.contestant-details {
  max-height: 90vh;
  overflow-y: auto;
}

.photo-grid {
  min-height: 200px;
}

.photo-card {
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
}

.photo-card:hover {
  transform: scale(1.05);
}

.photo-card:hover .photo-overlay {
  opacity: 0.7 !important;
}

.photo-overlay {
  transition: opacity 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.photo-carousel .v-img {
  cursor: pointer;
}
</style>