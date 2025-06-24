import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

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
    const response = await apiClient.get('/api/videos/')
    return response.data
  }

  static async uploadVideo(formData: FormData, onProgress?: (progress: number) => void) {
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
    const response = await apiClient.post(`/api/videos/${videoId}/process/`, config)
    return response.data
  }

  // Contestant endpoints
  static async getContestants() {
    const response = await apiClient.get('/api/contestants/')
    return response.data
  }

  static async getContestant(id: string) {
    const response = await apiClient.get(`/api/contestants/${id}/`)
    return response.data
  }

  // Results endpoints
  static async getResults(videoId?: string) {
    const url = videoId ? `/api/results/?video=${videoId}` : '/api/results/'
    const response = await apiClient.get(url)
    return response.data
  }

  static async exportResults(videoId: string, format: 'csv' | 'json') {
    const response = await apiClient.get(`/api/results/${videoId}/export/`, {
      params: { format },
      responseType: 'blob'
    })
    return response.data
  }

  // Settings endpoints
  static async getSettings() {
    const response = await apiClient.get('/api/settings/')
    return response.data
  }

  static async updateSettings(settings: any) {
    const response = await apiClient.put('/api/settings/', settings)
    return response.data
  }

  // System status
  static async getSystemStatus() {
    const response = await apiClient.get('/api/system/status/')
    return response.data
  }
}

export default apiClient