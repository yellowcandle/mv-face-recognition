import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { MockApiService } from './mockApi'

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Development mode flag
const isDevelopment = import.meta.env.DEV
const useMockApi = import.meta.env.VITE_USE_MOCK_API === 'true' || isDevelopment

// Request interceptor
apiClient.interceptors.request.use(
  (config: AxiosRequestConfig) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('auth_token')
      // Redirect to login if needed
    }
    return Promise.reject(error)
  }
)

// API service class
export class ApiService {
  // Video endpoints
  static async getVideos() {
    if (useMockApi) {
      return MockApiService.getVideos()
    }
    const response = await apiClient.get('/api/videos/')
    return response.data
  }

  static async uploadVideo(formData: FormData, onProgress?: (progress: number) => void) {
    if (useMockApi) {
      return MockApiService.uploadVideo(formData, onProgress)
    }
    const response = await apiClient.post('/api/videos/upload/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      }
    })
    return response.data
  }

  static async processVideo(videoId: string, config: any) {
    if (useMockApi) {
      return MockApiService.processVideo(videoId, config)
    }
    const response = await apiClient.post(`/api/videos/${videoId}/process/`, config)
    return response.data
  }

  // Contestant endpoints
  static async getContestants() {
    if (useMockApi) {
      return MockApiService.getContestants()
    }
    const response = await apiClient.get('/api/contestants/')
    return response.data
  }

  static async getContestant(id: string) {
    if (useMockApi) {
      return MockApiService.getContestant(id)
    }
    const response = await apiClient.get(`/api/contestants/${id}/`)
    return response.data
  }

  // Results endpoints
  static async getResults(videoId?: string) {
    if (useMockApi) {
      return MockApiService.getResults(videoId)
    }
    const url = videoId ? `/api/results/?video=${videoId}` : '/api/results/'
    const response = await apiClient.get(url)
    return response.data
  }

  static async exportResults(videoId: string, format: 'csv' | 'json') {
    if (useMockApi) {
      return MockApiService.exportResults(videoId, format)
    }
    const response = await apiClient.get(`/api/results/${videoId}/export/`, {
      params: { format },
      responseType: 'blob'
    })
    return response.data
  }

  // Settings endpoints
  static async getSettings() {
    if (useMockApi) {
      return MockApiService.getSettings()
    }
    const response = await apiClient.get('/api/settings/')
    return response.data
  }

  static async updateSettings(settings: any) {
    if (useMockApi) {
      return MockApiService.updateSettings(settings)
    }
    const response = await apiClient.put('/api/settings/', settings)
    return response.data
  }

  // Processing job endpoints
  static async getProcessingJobs() {
    if (useMockApi) {
      return MockApiService.getProcessingJobs()
    }
    const response = await apiClient.get('/api/process/jobs/')
    return response.data
  }

  static async getProcessingJob(jobId: string) {
    if (useMockApi) {
      return MockApiService.getProcessingJob(jobId)
    }
    const response = await apiClient.get(`/api/process/jobs/${jobId}/`)
    return response.data
  }

  static async cancelJob(jobId: string) {
    if (useMockApi) {
      return MockApiService.cancelJob(jobId)
    }
    const response = await apiClient.post(`/api/process/jobs/${jobId}/cancel/`)
    return response.data
  }

  static async getJobResults(jobId: string) {
    if (useMockApi) {
      return MockApiService.getJobResults(jobId)
    }
    const response = await apiClient.get(`/api/process/jobs/${jobId}/results/`)
    return response.data
  }

  static async downloadJobFile(jobId: string, fileType: 'annotated-video' | 'csv') {
    if (useMockApi) {
      return MockApiService.downloadJobFile(jobId, fileType)
    }
    const response = await apiClient.get(`/api/process/jobs/${jobId}/download/${fileType}/`, {
      responseType: 'blob'
    })
    return response.data
  }

  // Analytics endpoints
  static async getAnalyticsData(videoId?: string) {
    if (useMockApi) {
      return MockApiService.getAnalyticsData(videoId)
    }
    const url = videoId ? `/api/analytics/?video=${videoId}` : '/api/analytics/'
    const response = await apiClient.get(url)
    return response.data
  }

  static async getContestantTimeline(contestantId: string, videoId?: string) {
    if (useMockApi) {
      return MockApiService.getContestantTimeline(contestantId, videoId)
    }
    const params = videoId ? { video: videoId } : {}
    const response = await apiClient.get(`/api/analytics/contestant/${contestantId}/timeline/`, { params })
    return response.data
  }

  // System status
  static async getSystemStatus() {
    if (useMockApi) {
      return MockApiService.getSystemStatus()
    }
    const response = await apiClient.get('/api/system/status/')
    return response.data
  }

  // Health check
  static async healthCheck() {
    if (useMockApi) {
      return MockApiService.healthCheck()
    }
    try {
      const response = await apiClient.get('/api/health/')
      return { status: 'connected', data: response.data }
    } catch (error) {
      return { status: 'disconnected', error }
    }
  }
}

export default apiClient