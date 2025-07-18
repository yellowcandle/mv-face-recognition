<template>
  <div class="settings">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h3 mb-6">Settings</h1>
        <p class="text-body-1 text-grey mb-6">
          Configure face detection, recognition, and video processing parameters.
        </p>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" lg="8">
        <!-- Settings Form -->
        <v-form ref="settingsForm" v-model="formValid">
          <!-- Face Detection Settings -->
          <v-card class="mb-6">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2">mdi-face-agent</v-icon>
              Face Detection
            </v-card-title>
            
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="settings.face_detection.model_name"
                    :items="detectionModels"
                    label="Detection Model"
                    variant="outlined"
                    :rules="[rules.required]"
                  />
                </v-col>
                
                <v-col cols="12" md="6">
                  <v-slider
                    v-model="settings.face_detection.detection_threshold"
                    label="Detection Threshold"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    thumb-label="always"
                    color="primary"
                  >
                    <template v-slot:append>
                      <v-text-field
                        v-model="settings.face_detection.detection_threshold"
                        type="number"
                        style="width: 80px"
                        density="compact"
                        hide-details
                        variant="outlined"
                        :rules="[rules.required, rules.threshold]"
                      />
                    </template>
                  </v-slider>
                  <div class="text-caption text-grey">
                    Minimum confidence score for face detection ({{ settings.face_detection.detection_threshold }})
                  </div>
                </v-col>
              </v-row>
              
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model.number="settings.face_detection.input_size[0]"
                    label="Input Width"
                    type="number"
                    variant="outlined"
                    suffix="px"
                    :rules="[rules.required, rules.positiveNumber]"
                  />
                </v-col>
                
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model.number="settings.face_detection.input_size[1]"
                    label="Input Height"
                    type="number"
                    variant="outlined"
                    suffix="px"
                    :rules="[rules.required, rules.positiveNumber]"
                  />
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
          
          <!-- Face Matching Settings -->
          <v-card class="mb-6">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2">mdi-face-recognition</v-icon>
              Face Matching
            </v-card-title>
            
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-slider
                    v-model="settings.face_matching.similarity_threshold"
                    label="Similarity Threshold"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    thumb-label="always"
                    color="primary"
                  >
                    <template v-slot:append>
                      <v-text-field
                        v-model="settings.face_matching.similarity_threshold"
                        type="number"
                        style="width: 80px"
                        density="compact"
                        hide-details
                        variant="outlined"
                        :rules="[rules.required, rules.threshold]"
                      />
                    </template>
                  </v-slider>
                  <div class="text-caption text-grey">
                    Minimum similarity score for face matching ({{ settings.face_matching.similarity_threshold }})
                  </div>
                </v-col>
                
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model.number="settings.face_matching.max_results"
                    label="Max Results"
                    type="number"
                    variant="outlined"
                    :rules="[rules.required, rules.positiveNumber]"
                  />
                  <div class="text-caption text-grey">
                    Maximum number of similar faces to return
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
          
          <!-- Video Processing Settings -->
          <v-card class="mb-6">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2">mdi-video-settings</v-icon>
              Video Processing
            </v-card-title>
            
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-slider
                    v-model="settings.video_processing.frame_skip"
                    label="Frame Skip"
                    min="1"
                    max="30"
                    step="1"
                    thumb-label="always"
                    color="primary"
                  >
                    <template v-slot:append>
                      <v-text-field
                        v-model="settings.video_processing.frame_skip"
                        type="number"
                        style="width: 60px"
                        density="compact"
                        hide-details
                        variant="outlined"
                        :rules="[rules.required, rules.positiveNumber]"
                      />
                    </template>
                  </v-slider>
                  <div class="text-caption text-grey">
                    Process every {{ settings.video_processing.frame_skip }} frame{{ settings.video_processing.frame_skip !== 1 ? 's' : '' }}
                  </div>
                </v-col>
                
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model.number="settings.video_processing.output_fps"
                    label="Output FPS"
                    type="number"
                    variant="outlined"
                    :rules="[rules.required, rules.positiveNumber]"
                  />
                  <div class="text-caption text-grey">
                    Frame rate for annotated video output
                  </div>
                </v-col>
              </v-row>
              
              <v-row>
                <v-col cols="12" md="6">
                  <v-slider
                    v-model="settings.video_processing.annotation_font_scale"
                    label="Font Scale"
                    min="0.3"
                    max="2.0"
                    step="0.1"
                    thumb-label="always"
                    color="primary"
                  >
                    <template v-slot:append>
                      <v-text-field
                        v-model="settings.video_processing.annotation_font_scale"
                        type="number"
                        style="width: 60px"
                        density="compact"
                        hide-details
                        variant="outlined"
                        :rules="[rules.required, rules.positiveNumber]"
                      />
                    </template>
                  </v-slider>
                  <div class="text-caption text-grey">
                    Size of text annotations on video
                  </div>
                </v-col>
                
                <v-col cols="12" md="6">
                  <v-slider
                    v-model="settings.video_processing.annotation_thickness"
                    label="Line Thickness"
                    min="1"
                    max="10"
                    step="1"
                    thumb-label="always"
                    color="primary"
                  >
                    <template v-slot:append>
                      <v-text-field
                        v-model="settings.video_processing.annotation_thickness"
                        type="number"
                        style="width: 60px"
                        density="compact"
                        hide-details
                        variant="outlined"
                        :rules="[rules.required, rules.positiveNumber]"
                      />
                    </template>
                  </v-slider>
                  <div class="text-caption text-grey">
                    Thickness of bounding box lines
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-form>
      </v-col>
      
      <v-col cols="12" lg="4">
        <!-- Actions Panel -->
        <v-card>
          <v-card-title>Actions</v-card-title>
          <v-card-text>
            <div class="d-flex flex-column gap-3">
              <v-btn
                color="primary"
                block
                prepend-icon="mdi-content-save"
                :loading="saving"
                :disabled="!formValid || !hasChanges"
                @click="saveSettings"
              >
                Save Settings
              </v-btn>
              
              <v-btn
                color="secondary"
                variant="outlined"
                block
                prepend-icon="mdi-refresh"
                :loading="loading"
                @click="loadSettings"
              >
                Reload Settings
              </v-btn>
              
              <v-btn
                color="warning"
                variant="outlined"
                block
                prepend-icon="mdi-restore"
                @click="resetToDefaults"
              >
                Reset to Defaults
              </v-btn>
              
              <v-divider class="my-2"></v-divider>
              
              <v-btn
                color="info"
                variant="outlined"
                block
                prepend-icon="mdi-download"
                @click="exportSettings"
              >
                Export Settings
              </v-btn>
              
              <v-btn
                color="info"
                variant="outlined"
                block
                prepend-icon="mdi-upload"
                @click="$refs.importFile.click()"
              >
                Import Settings
              </v-btn>
              
              <input
                ref="importFile"
                type="file"
                accept=".json"
                hidden
                @change="importSettings"
              />
            </div>
          </v-card-text>
        </v-card>
        
        <!-- Current Status -->
        <v-card class="mt-4">
          <v-card-title>Current Status</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>Last Saved</v-list-item-title>
                <v-list-item-subtitle>{{ lastSaved || 'Never' }}</v-list-item-subtitle>
              </v-list-item>
              
              <v-list-item>
                <v-list-item-title>Changes</v-list-item-title>
                <v-list-item-subtitle>
                  <v-chip
                    :color="hasChanges ? 'warning' : 'success'"
                    size="small"
                    variant="flat"
                  >
                    {{ hasChanges ? 'Unsaved Changes' : 'All Saved' }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
        
        <!-- Settings Preview -->
        <v-card class="mt-4">
          <v-card-title>Settings Preview</v-card-title>
          <v-card-text>
            <v-expansion-panels variant="accordion">
              <v-expansion-panel title="Face Detection">
                <v-expansion-panel-text>
                  <pre class="text-caption">{{ JSON.stringify(settings.face_detection, null, 2) }}</pre>
                </v-expansion-panel-text>
              </v-expansion-panel>
              
              <v-expansion-panel title="Face Matching">
                <v-expansion-panel-text>
                  <pre class="text-caption">{{ JSON.stringify(settings.face_matching, null, 2) }}</pre>
                </v-expansion-panel-text>
              </v-expansion-panel>
              
              <v-expansion-panel title="Video Processing">
                <v-expansion-panel-text>
                  <pre class="text-caption">{{ JSON.stringify(settings.video_processing, null, 2) }}</pre>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    
    <!-- Success/Error Messages -->
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
    
    <v-snackbar
      v-model="showErrorMessage"
      color="error"
      timeout="6000"
    >
      {{ errorMessage }}
      <template v-slot:actions>
        <v-btn @click="showErrorMessage = false">Close</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ApiService } from '@/core/services/api'
import type { AppSettings } from '@/core/types/api'

// Form validation
const settingsForm = ref()
const formValid = ref(true)

// State
const loading = ref(false)
const saving = ref(false)
const originalSettings = ref<AppSettings | null>(null)
const lastSaved = ref<string | null>(null)
const showSuccessMessage = ref(false)
const showErrorMessage = ref(false)
const successMessage = ref('')
const errorMessage = ref('')

// Settings data
const settings = ref<AppSettings>({
  face_detection: {
    model_name: 'buffalo_l',
    detection_threshold: 0.5,
    input_size: [640, 640]
  },
  face_matching: {
    similarity_threshold: 0.6,
    max_results: 5
  },
  video_processing: {
    frame_skip: 5,
    output_fps: 24,
    annotation_font_scale: 0.7,
    annotation_thickness: 2
  }
})

// Detection model options
const detectionModels = [
  { title: 'Buffalo L (Recommended)', value: 'buffalo_l' },
  { title: 'Buffalo M', value: 'buffalo_m' },
  { title: 'Buffalo S', value: 'buffalo_s' }
]

// Form validation rules
const rules = {
  required: (value: any) => !!value || 'This field is required',
  threshold: (value: number) => (value >= 0.1 && value <= 1.0) || 'Must be between 0.1 and 1.0',
  positiveNumber: (value: number) => value > 0 || 'Must be a positive number'
}

// Computed
const hasChanges = computed(() => {
  return originalSettings.value && JSON.stringify(settings.value) !== JSON.stringify(originalSettings.value)
})

// Methods
const loadSettings = async () => {
  try {
    loading.value = true
    const data = await ApiService.getSettings()
    settings.value = data
    originalSettings.value = JSON.parse(JSON.stringify(data))
  } catch (error) {
    errorMessage.value = 'Failed to load settings'
    showErrorMessage.value = true
    console.error('Error loading settings:', error)
  } finally {
    loading.value = false
  }
}

const saveSettings = async () => {
  if (!formValid.value) return
  
  try {
    saving.value = true
    await ApiService.updateSettings(settings.value)
    originalSettings.value = JSON.parse(JSON.stringify(settings.value))
    lastSaved.value = new Date().toLocaleString()
    successMessage.value = 'Settings saved successfully!'
    showSuccessMessage.value = true
  } catch (error) {
    errorMessage.value = 'Failed to save settings'
    showErrorMessage.value = true
    console.error('Error saving settings:', error)
  } finally {
    saving.value = false
  }
}

const resetToDefaults = () => {
  settings.value = {
    face_detection: {
      model_name: 'buffalo_l',
      detection_threshold: 0.5,
      input_size: [640, 640]
    },
    face_matching: {
      similarity_threshold: 0.6,
      max_results: 5
    },
    video_processing: {
      frame_skip: 5,
      output_fps: 24,
      annotation_font_scale: 0.7,
      annotation_thickness: 2
    }
  }
  
  successMessage.value = 'Settings reset to defaults'
  showSuccessMessage.value = true
}

const exportSettings = () => {
  const dataStr = JSON.stringify(settings.value, null, 2)
  const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr)
  
  const exportFileDefaultName = `mv-face-recognition-settings-${new Date().toISOString().split('T')[0]}.json`
  
  const linkElement = document.createElement('a')
  linkElement.setAttribute('href', dataUri)
  linkElement.setAttribute('download', exportFileDefaultName)
  linkElement.click()
  
  successMessage.value = 'Settings exported successfully!'
  showSuccessMessage.value = true
}

const importSettings = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (!file) return
  
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const imported = JSON.parse(e.target?.result as string)
      settings.value = imported
      successMessage.value = 'Settings imported successfully!'
      showSuccessMessage.value = true
    } catch (error) {
      errorMessage.value = 'Invalid settings file format'
      showErrorMessage.value = true
    }
  }
  reader.readAsText(file)
  
  // Reset input
  target.value = ''
}

// Load settings on mount
onMounted(() => {
  loadSettings()
})

// Watch for changes to validate form
watch(settings, () => {
  settingsForm.value?.validate()
}, { deep: true })
</script>

<style scoped>
.gap-3 > * {
  margin-bottom: 0.75rem;
}

.gap-3 > *:last-child {
  margin-bottom: 0;
}

pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  background: rgba(var(--v-theme-surface-variant), 0.5);
  padding: 8px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}
</style>