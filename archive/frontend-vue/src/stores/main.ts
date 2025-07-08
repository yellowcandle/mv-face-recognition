import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ApiService } from '@/core/services/api'
import type { SystemStatus, AppSettings } from '@/core/types/api'

export const useMainStore = defineStore('main', () => {
  // State
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const systemStatus = ref<SystemStatus>({
    chromadb_connected: false,
    model_loaded: false,
    services_running: false,
    video_count: 0,
    contestant_count: 0,
    processing_jobs: 0
  })
  const settings = ref<AppSettings | null>(null)
  const apiConnected = ref(false)
  const lastHealthCheck = ref<Date | null>(null)

  // Getters
  const isSystemHealthy = computed(() => {
    return systemStatus.value.chromadb_connected &&
           systemStatus.value.model_loaded &&
           systemStatus.value.services_running
  })

  const dashboardStats = computed(() => ({
    contestants: systemStatus.value.contestant_count,
    videos: systemStatus.value.video_count,
    processingJobs: systemStatus.value.processing_jobs,
    systemHealthy: isSystemHealthy.value
  }))

  // Actions
  const setLoading = (loading: boolean) => {
    isLoading.value = loading
  }

  const setError = (errorMessage: string | null) => {
    error.value = errorMessage
  }

  const clearError = () => {
    error.value = null
  }

  const checkApiHealth = async () => {
    try {
      const result = await ApiService.healthCheck()
      apiConnected.value = result.status === 'connected'
      lastHealthCheck.value = new Date()
      return result
    } catch (err) {
      apiConnected.value = false
      console.error('API health check failed:', err)
      return { status: 'disconnected', error: err }
    }
  }

  const fetchSystemStatus = async () => {
    try {
      isLoading.value = true
      clearError()
      const status = await ApiService.getSystemStatus()
      systemStatus.value = status
    } catch (err) {
      setError('Failed to fetch system status')
      console.error('System status error:', err)
    } finally {
      isLoading.value = false
    }
  }

  const loadSettings = async () => {
    try {
      const appSettings = await ApiService.getSettings()
      settings.value = appSettings
    } catch (err) {
      console.error('Failed to load settings:', err)
      setError('Failed to load application settings')
    }
  }

  const updateSettings = async (newSettings: AppSettings) => {
    try {
      const updated = await ApiService.updateSettings(newSettings)
      settings.value = updated
      return updated
    } catch (err) {
      console.error('Failed to update settings:', err)
      setError('Failed to update settings')
      throw err
    }
  }

  const initializeApp = async () => {
    try {
      setLoading(true)
      clearError()
      
      // Check API health first
      await checkApiHealth()
      
      // Load initial data
      await Promise.all([
        fetchSystemStatus(),
        loadSettings()
      ])
      
    } catch (err) {
      console.error('App initialization failed:', err)
      setError('Failed to initialize application')
    } finally {
      setLoading(false)
    }
  }

  // Periodic health checks
  const startHealthChecks = () => {
    // Check every 30 seconds
    const interval = setInterval(async () => {
      await checkApiHealth()
    }, 30000)
    
    return () => clearInterval(interval)
  }

  return {
    // State
    isLoading,
    error,
    systemStatus,
    settings,
    apiConnected,
    lastHealthCheck,
    
    // Getters
    isSystemHealthy,
    dashboardStats,
    
    // Actions
    setLoading,
    setError,
    clearError,
    checkApiHealth,
    fetchSystemStatus,
    loadSettings,
    updateSettings,
    initializeApp,
    startHealthChecks
  }
})