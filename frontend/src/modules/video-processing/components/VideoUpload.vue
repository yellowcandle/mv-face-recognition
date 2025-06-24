<template>
  <v-card class="video-upload">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-video-plus</v-icon>
      Video Upload
    </v-card-title>
    
    <v-card-text>
      <!-- Drag and Drop Zone -->
      <div
        ref="dropZone"
        class="drop-zone"
        :class="{ 
          'drag-over': isDragOver,
          'uploading': isUploading 
        }"
        @click="openFileDialog"
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
      >
        <div v-if="!isUploading" class="drop-zone-content">
          <v-icon size="64" color="primary" class="mb-4">
            {{ isDragOver ? 'mdi-cloud-upload' : 'mdi-video-plus' }}
          </v-icon>
          
          <h3 class="text-h6 mb-2">
            {{ isDragOver ? 'Drop video here' : 'Upload Video File' }}
          </h3>
          
          <p class="text-body-2 text-grey mb-4">
            Drop video files here or click to browse
          </p>
          
          <v-btn
            color="primary"
            variant="outlined"
            prepend-icon="mdi-folder-open"
          >
            Choose Files
          </v-btn>
          
          <div class="mt-4">
            <v-chip
              v-for="format in supportedFormats"
              :key="format"
              size="small"
              class="ma-1"
              color="primary"
              variant="outlined"
            >
              {{ format.toUpperCase() }}
            </v-chip>
          </div>
        </div>
        
        <!-- Upload Progress -->
        <div v-else class="upload-progress">
          <v-progress-circular
            :value="uploadProgress"
            size="80"
            width="8"
            color="primary"
            class="mb-4"
          >
            <span class="text-h6">{{ Math.round(uploadProgress) }}%</span>
          </v-progress-circular>
          
          <h3 class="text-h6 mb-2">Uploading...</h3>
          <p class="text-body-2">{{ currentFileName }}</p>
        </div>
      </div>
      
      <!-- File Input (Hidden) -->
      <input
        ref="fileInput"
        type="file"
        hidden
        multiple
        accept="video/*"
        @change="handleFileSelect"
      />
      
      <!-- Upload Queue -->
      <div v-if="uploadQueue.length > 0" class="mt-6">
        <h4 class="text-subtitle-1 mb-3">Upload Queue</h4>
        
        <v-list>
          <v-list-item
            v-for="(file, index) in uploadQueue"
            :key="index"
            class="upload-queue-item"
          >
            <template v-slot:prepend>
              <v-avatar color="primary" variant="tonal">
                <v-icon>mdi-video</v-icon>
              </v-avatar>
            </template>
            
            <v-list-item-title>{{ file.name }}</v-list-item-title>
            <v-list-item-subtitle>
              {{ formatFileSize(file.size) }} • {{ getFileExtension(file.name) }}
            </v-list-item-subtitle>
            
            <template v-slot:append>
              <v-btn
                icon="mdi-close"
                size="small"
                variant="text"
                @click="removeFromQueue(index)"
              />
            </template>
          </v-list-item>
        </v-list>
        
        <div class="d-flex justify-end mt-4">
          <v-btn
            color="error"
            variant="outlined"
            prepend-icon="mdi-delete"
            class="mr-2"
            @click="clearQueue"
          >
            Clear All
          </v-btn>
          
          <v-btn
            color="primary"
            prepend-icon="mdi-upload"
            :loading="isUploading"
            :disabled="uploadQueue.length === 0"
            @click="startUpload"
          >
            Upload {{ uploadQueue.length }} File{{ uploadQueue.length !== 1 ? 's' : '' }}
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
      
      <!-- Success Display -->
      <v-alert
        v-if="successMessage"
        type="success"
        variant="tonal"
        closable
        class="mt-4"
        @click:close="successMessage = ''"
      >
        {{ successMessage }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useVideoProcessingStore } from '../stores/videoProcessing'

const emit = defineEmits<{
  'upload-complete': [files: File[]]
  'upload-start': [files: File[]]
}>()

const videoStore = useVideoProcessingStore()

// State
const dropZone = ref<HTMLElement>()
const fileInput = ref<HTMLInputElement>()
const isDragOver = ref(false)
const uploadQueue = ref<File[]>([])
const currentFileName = ref('')
const error = ref('')
const successMessage = ref('')

// Computed
const isUploading = computed(() => videoStore.uploadProgress > 0)
const uploadProgress = computed(() => videoStore.uploadProgress)

const supportedFormats = ['.mp4', '.avi', '.mov', '.mkv', '.wmv']

// Methods
const openFileDialog = () => {
  if (!isUploading.value) {
    fileInput.value?.click()
  }
}

const handleDragOver = (event: DragEvent) => {
  if (isUploading.value) return
  
  event.preventDefault()
  isDragOver.value = true
}

const handleDragLeave = (event: DragEvent) => {
  if (isUploading.value) return
  
  event.preventDefault()
  // Only set to false if leaving the drop zone entirely
  if (!dropZone.value?.contains(event.relatedTarget as Node)) {
    isDragOver.value = false
  }
}

const handleDrop = (event: DragEvent) => {
  if (isUploading.value) return
  
  event.preventDefault()
  isDragOver.value = false
  
  const files = Array.from(event.dataTransfer?.files || [])
  addFilesToQueue(files)
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files || [])
  addFilesToQueue(files)
  
  // Reset input
  if (target) target.value = ''
}

const addFilesToQueue = (files: File[]) => {
  const validFiles = files.filter(file => {
    // Check file type
    const extension = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!supportedFormats.includes(extension)) {
      error.value = `Unsupported file format: ${extension}. Supported formats: ${supportedFormats.join(', ')}`
      return false
    }
    
    // Check file size (100MB limit)
    const maxSize = 100 * 1024 * 1024
    if (file.size > maxSize) {
      error.value = `File too large: ${file.name}. Maximum size: 100MB`
      return false
    }
    
    // Check if already in queue
    if (uploadQueue.value.some(queueFile => queueFile.name === file.name)) {
      return false
    }
    
    return true
  })
  
  uploadQueue.value.push(...validFiles)
  
  if (validFiles.length > 0) {
    clearError()
  }
}

const removeFromQueue = (index: number) => {
  uploadQueue.value.splice(index, 1)
}

const clearQueue = () => {
  uploadQueue.value = []
}

const startUpload = async () => {
  if (uploadQueue.value.length === 0) return
  
  const filesToUpload = [...uploadQueue.value]
  clearQueue()
  clearError()
  
  emit('upload-start', filesToUpload)
  
  try {
    for (const file of filesToUpload) {
      currentFileName.value = file.name
      
      await videoStore.uploadVideo(file, (progress) => {
        // Progress handled by store
      })
    }
    
    successMessage.value = `Successfully uploaded ${filesToUpload.length} file${filesToUpload.length !== 1 ? 's' : ''}`
    emit('upload-complete', filesToUpload)
    
  } catch (err) {
    error.value = 'Upload failed. Please try again.'
    console.error('Upload error:', err)
  } finally {
    currentFileName.value = ''
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const getFileExtension = (filename: string): string => {
  return filename.split('.').pop()?.toUpperCase() || ''
}

const clearError = () => {
  error.value = ''
  videoStore.clearError()
}
</script>

<style scoped>
.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 12px;
  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: rgba(var(--v-theme-surface), 0.5);
}

.drop-zone:hover {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.05);
}

.drop-zone.drag-over {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
  transform: scale(1.02);
}

.drop-zone.uploading {
  border-color: rgb(var(--v-theme-primary));
  cursor: not-allowed;
}

.drop-zone-content,
.upload-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.upload-queue-item {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  margin-bottom: 8px;
}
</style>