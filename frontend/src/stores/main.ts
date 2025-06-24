import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ApiService } from '@/core/services/api'

export const useMainStore = defineStore('main', () => {
  // State
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const systemStatus = ref({
    chromadb_connected: false,
    model_loaded: false,
    services_running: false
  })

  // Getters
  const isSystemHealthy = computed(() => {
    return systemStatus.value.chromadb_connected &&
           systemStatus.value.model_loaded &&
           systemStatus.value.services_running
  })

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

  return {
    // State
    isLoading,
    error,
    systemStatus,
    
    // Getters
    isSystemHealthy,
    
    // Actions
    setLoading,
    setError,
    clearError,
    fetchSystemStatus
  }
})