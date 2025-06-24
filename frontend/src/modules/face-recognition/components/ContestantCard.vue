<template>
  <v-card
    class="contestant-card"
    :class="{ 'selected': isSelected }"
    hover
    @click="$emit('click')"
  >
    <!-- Photo -->
    <div class="photo-container">
      <v-img
        v-if="contestant.photos.length > 0"
        :src="getPhotoUrl(contestant.photos[0])"
        :alt="contestant.name"
        height="120"
        cover
        class="contestant-photo"
      >
        <template v-slot:placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular indeterminate color="primary" />
          </div>
        </template>
        
        <template v-slot:error>
          <div class="d-flex align-center justify-center fill-height bg-grey-lighten-3">
            <v-icon size="40" color="grey">mdi-image-broken</v-icon>
          </div>
        </template>
      </v-img>
      
      <div v-else class="no-photo d-flex align-center justify-center">
        <v-icon size="60" color="grey-lighten-1">mdi-account</v-icon>
      </div>
      
      <!-- Photo Count Badge -->
      <v-badge
        v-if="contestant.photos.length > 1"
        :content="contestant.photos.length"
        color="primary"
        class="photo-badge"
      >
        <v-icon size="20" color="white">mdi-image-multiple</v-icon>
      </v-badge>
      
      <!-- Embedding Status Badge -->
      <v-chip
        :color="contestant.embedding_available ? 'success' : 'warning'"
        size="x-small"
        variant="flat"
        class="embedding-badge"
      >
        <v-icon
          start
          size="12"
        >
          {{ contestant.embedding_available ? 'mdi-check' : 'mdi-alert' }}
        </v-icon>
        {{ contestant.embedding_available ? 'Ready' : 'No Embed' }}
      </v-chip>
    </div>
    
    <!-- Content -->
    <v-card-text class="pa-3">
      <div class="text-center">
        <h4 class="text-subtitle-2 font-weight-bold text-truncate">
          {{ contestant.name }}
        </h4>
        
        <p class="text-caption text-grey mt-1 mb-0">
          ID: {{ contestant.id }}
        </p>
      </div>
    </v-card-text>
    
    <!-- Actions -->
    <v-card-actions class="pa-2">
      <v-btn
        size="small"
        variant="text"
        block
        @click.stop="$emit('view-details')"
      >
        <v-icon start size="16">mdi-information</v-icon>
        Details
      </v-btn>
    </v-card-actions>
    
    <!-- Selection Overlay -->
    <v-overlay
      v-if="isSelected"
      contained
      scrim="primary"
      opacity="0.2"
      class="selection-overlay"
    >
      <v-icon size="40" color="white">mdi-check-circle</v-icon>
    </v-overlay>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Contestant } from '@/core/types/api'

interface Props {
  contestant: Contestant
  selected?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'click': []
  'view-details': []
}>()

const isSelected = computed(() => props.selected)

const getPhotoUrl = (photoPath: string) => {
  // Convert backend photo path to accessible URL
  return `/api/contestants/photos/${photoPath}`
}
</script>

<style scoped>
.contestant-card {
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
}

.contestant-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.contestant-card.selected {
  border: 2px solid rgb(var(--v-theme-primary));
}

.photo-container {
  position: relative;
  height: 120px;
}

.no-photo {
  height: 120px;
  background: rgba(var(--v-theme-surface-variant), 0.5);
}

.contestant-photo {
  border-radius: 4px 4px 0 0;
}

.photo-badge {
  position: absolute;
  top: 8px;
  right: 8px;
}

.embedding-badge {
  position: absolute;
  bottom: 8px;
  left: 8px;
  font-size: 0.6rem !important;
  height: 20px !important;
}

.selection-overlay {
  border-radius: inherit;
}

.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>