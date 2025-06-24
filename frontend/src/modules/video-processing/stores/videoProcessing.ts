import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ApiService } from '@/core/services/api'
import type { 
  VideoInfo, 
  ProcessingJob, 
  ProcessingConfig, 
  ProcessingResult,
  ProcessingProgress 
} from '@/core/types/api'

export const useVideoProcessingStore = defineStore('videoProcessing', () => {
  // State
  const videos = ref<VideoInfo[]>([])
  const selectedVideo = ref<VideoInfo | null>(null)
  const loadingVideos = ref(false)
  
  // Processing state
  const currentJob = ref<ProcessingJob | null>(null)
  const processingJobs = ref<ProcessingJob[]>([])
  const processingProgress = ref<ProcessingProgress | null>(null)
  const processingResult = ref<ProcessingResult | null>(null)
  
  // UI state
  const isProcessing = ref(false)
  const uploadProgress = ref(0)
  const error = ref<string | null>(null)
  
  // Getters
  const hasVideos = computed(() => videos.value.length > 0)
  const canStartProcessing = computed(() => 
    selectedVideo.value && !isProcessing.value
  )
  const processingProgressPercent = computed(() => 
    processingProgress.value?.progress || 0
  )
  
  // Actions
  const loadVideos = async () => {
    try {
      loadingVideos.value = true
      error.value = null
      const videoList = await ApiService.getVideos()
      videos.value = videoList
    } catch (err) {
      error.value = 'Failed to load videos'
      console.error('Error loading videos:', err)
    } finally {
      loadingVideos.value = false
    }
  }
  
  const selectVideo = (video: VideoInfo) => {
    selectedVideo.value = video
    // Clear previous results when selecting new video
    processingResult.value = null
    processingProgress.value = null
  }
  
  const uploadVideo = async (file: File, onProgress?: (progress: number) => void) => {
    try {
      uploadProgress.value = 0
      error.value = null
      
      const formData = new FormData()
      formData.append('file', file)
      
      const result = await ApiService.uploadVideo(formData, (progress) => {
        uploadProgress.value = progress
        if (onProgress) onProgress(progress)
      })
      
      // Reload videos to include the new upload
      await loadVideos()
      
      return result
      
    } catch (err) {
      error.value = 'Failed to upload video'
      console.error('Error uploading video:', err)
      throw err
    } finally {
      uploadProgress.value = 0
    }
  }
  
  const startProcessing = async (config: ProcessingConfig) => {
    if (!selectedVideo.value) {
      throw new Error('No video selected')
    }
    
    try {
      isProcessing.value = true
      error.value = null
      processingResult.value = null
      processingProgress.value = null
      
      const job = await ApiService.processVideo(selectedVideo.value.id, config)
      currentJob.value = job
      processingJobs.value.unshift(job)
      
      return job
      
    } catch (err) {
      error.value = 'Failed to start processing'
      console.error('Error starting processing:', err)
      isProcessing.value = false
      throw err
    }
  }
  
  const updateProcessingProgress = (progress: ProcessingProgress) => {
    processingProgress.value = progress
    
    // Update job in the list
    if (currentJob.value && currentJob.value.job_id === progress.job_id) {
      currentJob.value.progress = progress.progress
      currentJob.value.current_frame = progress.current_frame
      currentJob.value.total_frames = progress.total_frames
      currentJob.value.faces_detected = progress.faces_detected
      currentJob.value.matches_found = progress.matches_found
    }
  }
  
  const completeProcessing = (result: ProcessingResult) => {
    processingResult.value = result
    isProcessing.value = false
    
    // Update job status
    if (currentJob.value && currentJob.value.job_id === result.job_id) {
      currentJob.value.status = 'completed'
      currentJob.value.progress = 100
      currentJob.value.completed_at = new Date().toISOString()
    }
  }
  
  const failProcessing = (jobId: string, errorMessage: string) => {
    isProcessing.value = false
    error.value = errorMessage
    
    // Update job status
    if (currentJob.value && currentJob.value.job_id === jobId) {
      currentJob.value.status = 'failed'
      currentJob.value.error_message = errorMessage
    }
  }
  
  const cancelProcessing = async () => {
    if (!currentJob.value) return
    
    try {
      await ApiService.cancelJob(currentJob.value.job_id)
      isProcessing.value = false
      currentJob.value = null
    } catch (err) {
      console.error('Error cancelling processing:', err)
    }
  }
  
  const getProcessingJobs = async () => {
    try {
      const jobs = await ApiService.getProcessingJobs()
      processingJobs.value = jobs
    } catch (err) {
      console.error('Error loading processing jobs:', err)
    }
  }
  
  const downloadAnnotatedVideo = async (jobId: string) => {
    try {
      const response = await fetch(`/api/process/jobs/${jobId}/download/annotated-video/`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `annotated_${jobId}.mp4`
        link.click()
        window.URL.revokeObjectURL(url)
      }
    } catch (err) {
      console.error('Error downloading video:', err)
    }
  }
  
  const downloadCsvResults = async (jobId: string) => {
    try {
      const response = await fetch(`/api/process/jobs/${jobId}/download/csv/`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `results_${jobId}.csv`
        link.click()
        window.URL.revokeObjectURL(url)
      }
    } catch (err) {
      console.error('Error downloading CSV:', err)
    }
  }
  
  const clearError = () => {
    error.value = null
  }
  
  const resetProcessing = () => {
    currentJob.value = null
    processingProgress.value = null
    processingResult.value = null
    isProcessing.value = false
    error.value = null
  }
  
  return {
    // State
    videos,
    selectedVideo,
    loadingVideos,
    currentJob,
    processingJobs,
    processingProgress,
    processingResult,
    isProcessing,
    uploadProgress,
    error,
    
    // Getters
    hasVideos,
    canStartProcessing,
    processingProgressPercent,
    
    // Actions
    loadVideos,
    selectVideo,
    uploadVideo,
    startProcessing,
    updateProcessingProgress,
    completeProcessing,
    failProcessing,
    cancelProcessing,
    getProcessingJobs,
    downloadAnnotatedVideo,
    downloadCsvResults,
    clearError,
    resetProcessing
  }
})