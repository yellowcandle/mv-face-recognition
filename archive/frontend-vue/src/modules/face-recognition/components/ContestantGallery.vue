<template>
  <v-card class="contestant-gallery">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-account-group</v-icon>
      Contestant Gallery
      <v-spacer></v-spacer>
      
      <!-- Stats Chips -->
      <v-chip
        color="primary"
        size="small"
        variant="flat"
        class="mr-2"
      >
        {{ contestantCount }} Total
      </v-chip>
      
      <v-chip
        color="success"
        size="small"
        variant="flat"
        class="mr-2"
      >
        {{ contestantsWithEmbeddings.length }} With Embeddings
      </v-chip>
      
      <v-btn
        icon="mdi-refresh"
        variant="text"
        @click="refreshData"
        :loading="loading"
      />
    </v-card-title>
    
    <v-card-text>
      <!-- Search and Filter -->
      <div class="mb-6">
        <v-row>
          <v-col cols="12" md="8">
            <v-text-field
              v-model="searchQuery"
              label="Search contestants..."
              prepend-inner-icon="mdi-magnify"
              variant="outlined"
              density="compact"
              clearable
              @click:clear="clearSearch"
            />
          </v-col>
          
          <v-col cols="12" md="4">
            <v-select
              v-model="viewMode"
              :items="viewModes"
              label="View Mode"
              variant="outlined"
              density="compact"
            />
          </v-col>
        </v-row>
        
        <!-- Filter Chips -->
        <div class="d-flex flex-wrap gap-2 mt-2">
          <v-chip
            :color="showOnlyWithEmbeddings ? 'primary' : 'default'"
            :variant="showOnlyWithEmbeddings ? 'flat' : 'outlined'"
            @click="showOnlyWithEmbeddings = !showOnlyWithEmbeddings"
          >
            <v-icon start>{{ showOnlyWithEmbeddings ? 'mdi-check' : 'mdi-filter' }}</v-icon>
            With Embeddings Only
          </v-chip>
          
          <v-chip
            v-if="searchQuery"
            color="info"
            variant="flat"
            closable
            @click:close="clearSearch"
          >
            Search: "{{ searchQuery }}"
          </v-chip>
        </div>
      </div>
      
      <!-- Loading State -->
      <div v-if="loading" class="text-center py-8">
        <v-progress-circular
          indeterminate
          size="60"
          color="primary"
        />
        <p class="mt-4 text-body-1">Loading contestants...</p>
      </div>
      
      <!-- Grid View -->
      <div v-else-if="viewMode === 'grid'" class="contestant-grid">
        <v-row>
          <v-col
            v-for="contestant in displayedContestants"
            :key="contestant.id"
            cols="6"
            sm="4"
            md="3"
            lg="2"
          >
            <ContestantCard
              :contestant="contestant"
              @click="selectContestant(contestant)"
              @view-details="openContestantDialog(contestant)"
            />
          </v-col>
        </v-row>
      </div>
      
      <!-- List View -->
      <div v-else-if="viewMode === 'list'" class="contestant-list">
        <v-list>
          <v-list-item
            v-for="contestant in displayedContestants"
            :key="contestant.id"
            @click="selectContestant(contestant)"
          >
            <template v-slot:prepend>
              <v-avatar size="50">
                <v-img
                  v-if="contestant.photos.length > 0"
                  :src="getPhotoUrl(contestant.photos[0])"
                  :alt="contestant.name"
                />
                <v-icon v-else>mdi-account</v-icon>
              </v-avatar>
            </template>
            
            <v-list-item-title>{{ contestant.name }}</v-list-item-title>
            <v-list-item-subtitle>
              ID: {{ contestant.id }} • 
              {{ contestant.photos.length }} photo{{ contestant.photos.length !== 1 ? 's' : '' }}
            </v-list-item-subtitle>
            
            <template v-slot:append>
              <v-chip
                :color="contestant.embedding_available ? 'success' : 'warning'"
                size="small"
                variant="flat"
              >
                {{ contestant.embedding_available ? 'Ready' : 'No Embedding' }}
              </v-chip>
              
              <v-btn
                icon="mdi-information"
                size="small"
                variant="text"
                @click.stop="openContestantDialog(contestant)"
              />
            </template>
          </v-list-item>
        </v-list>
      </div>
      
      <!-- Alphabetical View -->
      <div v-else-if="viewMode === 'alphabetical'" class="contestant-alphabetical">
        <div
          v-for="(contestants, letter) in contestantsByLetter"
          :key="letter"
          class="letter-group mb-6"
        >
          <h3 class="text-h6 mb-3 font-weight-bold text-primary">{{ letter }}</h3>
          
          <v-row>
            <v-col
              v-for="contestant in contestants"
              :key="contestant.id"
              cols="6"
              sm="4"
              md="3"
              lg="2"
            >
              <ContestantCard
                :contestant="contestant"
                @click="selectContestant(contestant)"
                @view-details="openContestantDialog(contestant)"
              />
            </v-col>
          </v-row>
        </div>
      </div>
      
      <!-- Empty State -->
      <div v-if="!loading && displayedContestants.length === 0" class="text-center py-8">
        <v-icon size="80" color="grey-lighten-1">mdi-account-search</v-icon>
        <h3 class="text-h6 mt-4 mb-2">No Contestants Found</h3>
        <p class="text-body-2 text-grey mb-4">
          {{ searchQuery ? 'Try adjusting your search terms.' : 'No contestants available.' }}
        </p>
        <v-btn
          v-if="searchQuery"
          color="primary"
          @click="clearSearch"
        >
          Clear Search
        </v-btn>
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
    
    <!-- Selected Contestant Info -->
    <v-card-actions v-if="selectedContestant">
      <v-card variant="tonal" color="primary" class="w-100">
        <v-card-text>
          <div class="d-flex align-center">
            <v-avatar class="mr-3">
              <v-img
                v-if="selectedContestant.photos.length > 0"
                :src="getPhotoUrl(selectedContestant.photos[0])"
              />
              <v-icon v-else>mdi-account</v-icon>
            </v-avatar>
            
            <div class="flex-grow-1">
              <div class="font-weight-medium">Selected: {{ selectedContestant.name }}</div>
              <div class="text-caption">
                ID: {{ selectedContestant.id }} • 
                {{ selectedContestant.photos.length }} photos •
                {{ selectedContestant.embedding_available ? 'Ready for recognition' : 'No embedding' }}
              </div>
            </div>
            
            <v-btn
              icon="mdi-close"
              size="small"
              variant="text"
              @click="clearSelection"
            />
          </div>
        </v-card-text>
      </v-card>
    </v-card-actions>
  </v-card>
  
  <!-- Contestant Details Dialog -->
  <v-dialog v-model="showDetailsDialog" max-width="800">
    <ContestantDetails
      v-if="detailsContestant"
      :contestant="detailsContestant"
      @close="showDetailsDialog = false"
      @select="selectContestant"
    />
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useContestantsStore } from '@/stores/contestants'
import ContestantCard from './ContestantCard.vue'
import ContestantDetails from './ContestantDetails.vue'
import type { Contestant } from '@/core/types/api'

const emit = defineEmits<{
  'contestant-selected': [contestant: Contestant]
}>()

const contestantsStore = useContestantsStore()

// Local state
const viewMode = ref('grid')
const showOnlyWithEmbeddings = ref(false)
const showDetailsDialog = ref(false)
const detailsContestant = ref<Contestant | null>(null)

const viewModes = [
  { title: 'Grid View', value: 'grid' },
  { title: 'List View', value: 'list' },
  { title: 'Alphabetical', value: 'alphabetical' }
]

// Computed
const contestants = computed(() => contestantsStore.contestants)
const loading = computed(() => contestantsStore.loading)
const error = computed(() => contestantsStore.error)
const searchQuery = computed({
  get: () => contestantsStore.searchQuery,
  set: (value) => contestantsStore.setSearchQuery(value)
})
const selectedContestant = computed(() => contestantsStore.selectedContestant)
const contestantCount = computed(() => contestantsStore.contestantCount)
const contestantsWithEmbeddings = computed(() => contestantsStore.contestantsWithEmbeddings)
const contestantsByLetter = computed(() => contestantsStore.contestantsByLetter)

const displayedContestants = computed(() => {
  let filtered = contestantsStore.filteredContestants
  
  if (showOnlyWithEmbeddings.value) {
    filtered = filtered.filter(c => c.embedding_available)
  }
  
  return filtered
})

// Methods
const refreshData = async () => {
  await contestantsStore.loadContestants()
}

const selectContestant = (contestant: Contestant) => {
  contestantsStore.selectContestant(contestant)
  emit('contestant-selected', contestant)
}

const clearSelection = () => {
  contestantsStore.clearSelection()
}

const clearSearch = () => {
  contestantsStore.clearSearch()
}

const clearError = () => {
  contestantsStore.clearError()
}

const openContestantDialog = (contestant: Contestant) => {
  detailsContestant.value = contestant
  showDetailsDialog.value = true
}

const getPhotoUrl = (photoPath: string) => {
  // Convert backend photo path to accessible URL
  return `/api/contestants/photos/${photoPath}`
}

// Load data on mount
onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.contestant-gallery {
  min-height: 600px;
}

.contestant-grid,
.contestant-alphabetical {
  min-height: 400px;
}

.letter-group {
  border-left: 3px solid rgb(var(--v-theme-primary));
  padding-left: 1rem;
}

.gap-2 > * {
  margin: 0.25rem;
}
</style>