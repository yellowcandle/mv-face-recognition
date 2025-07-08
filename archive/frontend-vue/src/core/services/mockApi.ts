import type { 
  VideoInfo, 
  ProcessingJob, 
  ProcessingConfig, 
  ProcessingResult,
  Contestant,
  SystemStatus,
  AppSettings
} from '@/core/types/api'

// Mock data
const mockVideos: VideoInfo[] = [
  {
    id: '1',
    name: '《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅',
    filename: '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4',
    path: '/source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4',
    size: 157286400,
    duration_seconds: 210,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 6300,
    created_at: '2024-06-20T10:00:00Z'
  },
  {
    id: '2',
    name: '《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅',
    filename: '2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4',
    path: '/source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4',
    size: 142567890,
    duration_seconds: 195,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 5850,
    created_at: '2024-06-20T11:00:00Z'
  },
  {
    id: '3',
    name: '《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅',
    filename: '3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4',
    path: '/source/videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4',
    size: 167891234,
    duration_seconds: 225,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 6750,
    created_at: '2024-06-20T12:00:00Z'
  }
]

const mockContestants: Contestant[] = [
  { id: '1', name: 'Alice Chan', photos: ['alice1.jpg', 'alice2.jpg'], embedding_available: true, created_at: '2024-06-15T00:00:00Z' },
  { id: '2', name: 'Betty Wong', photos: ['betty1.jpg'], embedding_available: true, created_at: '2024-06-15T00:00:00Z' },
  { id: '3', name: 'Cathy Lee', photos: ['cathy1.jpg', 'cathy2.jpg', 'cathy3.jpg'], embedding_available: true, created_at: '2024-06-15T00:00:00Z' },
  { id: '4', name: 'Diana Zhang', photos: ['diana1.jpg'], embedding_available: false, created_at: '2024-06-15T00:00:00Z' },
  { id: '5', name: 'Eva Liu', photos: ['eva1.jpg', 'eva2.jpg'], embedding_available: true, created_at: '2024-06-15T00:00:00Z' }
]

const mockJobs: ProcessingJob[] = [
  {
    job_id: 'job_12345678',
    video_id: '1',
    status: 'completed',
    progress: 100,
    current_frame: 6300,
    total_frames: 6300,
    faces_detected: 1247,
    matches_found: 89,
    created_at: '2024-06-25T10:00:00Z',
    completed_at: '2024-06-25T10:15:30Z'
  },
  {
    job_id: 'job_87654321',
    video_id: '2',
    status: 'processing',
    progress: 45,
    current_frame: 2632,
    total_frames: 5850,
    faces_detected: 234,
    matches_found: 18,
    created_at: '2024-06-25T11:00:00Z'
  },
  {
    job_id: 'job_11223344',
    video_id: '3',
    status: 'failed',
    progress: 12,
    current_frame: 810,
    total_frames: 6750,
    faces_detected: 45,
    matches_found: 3,
    created_at: '2024-06-25T12:00:00Z',
    error_message: 'Video file corrupted at frame 810'
  }
]

const mockSystemStatus: SystemStatus = {
  chromadb_connected: true,
  model_loaded: true,
  services_running: true,
  video_count: 10,
  contestant_count: 96,
  processing_jobs: 1
}

const mockSettings: AppSettings = {
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
    annotation_font_scale: 0.8,
    annotation_thickness: 2
  }
}

// Utility functions
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
const generateId = () => 'mock_' + Math.random().toString(36).substr(2, 9)

// Mock API Service
export class MockApiService {
  static isDevelopment = import.meta.env.DEV

  // Video endpoints
  static async getVideos() {
    await delay(500) // Simulate network delay
    return mockVideos
  }

  static async uploadVideo(formData: FormData, onProgress?: (progress: number) => void) {
    // Simulate upload progress
    if (onProgress) {
      for (let progress = 0; progress <= 100; progress += 10) {
        await delay(200)
        onProgress(progress)
      }
    }
    
    const file = formData.get('file') as File
    const newVideo: VideoInfo = {
      id: generateId(),
      name: file.name.replace(/\.[^/.]+$/, ''), // Remove extension
      filename: file.name,
      path: `/source/videos/${file.name}`,
      size: file.size,
      duration_seconds: 180, // Mock duration
      fps: 30,
      width: 1920,
      height: 1080,
      frame_count: 5400,
      created_at: new Date().toISOString()
    }
    
    mockVideos.push(newVideo)
    return newVideo
  }

  static async processVideo(videoId: string, config: ProcessingConfig) {
    await delay(800)
    
    const video = mockVideos.find(v => v.id === videoId)
    if (!video) throw new Error('Video not found')
    
    const newJob: ProcessingJob = {
      job_id: generateId(),
      video_id: videoId,
      status: 'pending',
      progress: 0,
      current_frame: 0,
      total_frames: video.frame_count,
      faces_detected: 0,
      matches_found: 0,
      created_at: new Date().toISOString()
    }
    
    mockJobs.unshift(newJob)
    
    // Simulate processing start
    setTimeout(() => {
      newJob.status = 'processing'
    }, 1000)
    
    return newJob
  }

  // Contestant endpoints
  static async getContestants() {
    await delay(300)
    return mockContestants
  }

  static async getContestant(id: string) {
    await delay(200)
    const contestant = mockContestants.find(c => c.id === id)
    if (!contestant) throw new Error('Contestant not found')
    return contestant
  }

  // Results endpoints
  static async getResults(videoId?: string) {
    await delay(400)
    // Mock results data
    return {
      results: mockJobs.filter(job => job.status === 'completed' && (!videoId || job.video_id === videoId)),
      total_matches: 156,
      unique_contestants: 12
    }
  }

  static async exportResults(videoId: string, format: 'csv' | 'json') {
    await delay(1000)
    // Mock export data
    const data = format === 'csv' 
      ? 'frame,timestamp,contestant,confidence\n1,0.033,Alice Chan,0.95\n'
      : JSON.stringify({ results: [] })
    
    return new Blob([data], { type: format === 'csv' ? 'text/csv' : 'application/json' })
  }

  // Settings endpoints
  static async getSettings() {
    await delay(200)
    return mockSettings
  }

  static async updateSettings(settings: AppSettings) {
    await delay(300)
    Object.assign(mockSettings, settings)
    return mockSettings
  }

  // Processing job endpoints
  static async getProcessingJobs() {
    await delay(400)
    return mockJobs
  }

  static async getProcessingJob(jobId: string) {
    await delay(200)
    const job = mockJobs.find(j => j.job_id === jobId)
    if (!job) throw new Error('Job not found')
    return job
  }

  static async cancelJob(jobId: string) {
    await delay(300)
    const job = mockJobs.find(j => j.job_id === jobId)
    if (!job) throw new Error('Job not found')
    
    job.status = 'failed'
    job.error_message = 'Cancelled by user'
    return job
  }

  static async getJobResults(jobId: string) {
    await delay(500)
    // Mock detailed results
    return {
      job_id: jobId,
      video_id: mockJobs.find(j => j.job_id === jobId)?.video_id,
      total_frames: 6300,
      faces_detected: 1247,
      matches_found: 89,
      unique_contestants: 12,
      processing_time: 930.5,
      contestant_appearances: {
        '1': { contestant_id: '1', name: 'Alice Chan', total_appearances: 45, avg_confidence: 0.87 },
        '2': { contestant_id: '2', name: 'Betty Wong', total_appearances: 23, avg_confidence: 0.92 },
        '3': { contestant_id: '3', name: 'Cathy Lee', total_appearances: 21, avg_confidence: 0.89 }
      }
    }
  }

  static async downloadJobFile(jobId: string, fileType: 'annotated-video' | 'csv') {
    await delay(800)
    // Mock file download
    const content = fileType === 'csv' 
      ? 'frame,timestamp,contestant,confidence\n1,0.033,Alice Chan,0.95\n'
      : 'Mock video content'
    
    return new Blob([content], { 
      type: fileType === 'csv' ? 'text/csv' : 'video/mp4' 
    })
  }

  // Analytics endpoints
  static async getAnalyticsData(videoId?: string) {
    await delay(600)
    return {
      total_processing_time: 2847.3,
      total_faces_detected: 3456,
      total_matches_found: 234,
      top_contestants: [
        { name: 'Alice Chan', appearances: 45, avg_confidence: 0.87 },
        { name: 'Betty Wong', appearances: 34, avg_confidence: 0.92 },
        { name: 'Cathy Lee', appearances: 28, avg_confidence: 0.89 }
      ],
      processing_stats: {
        avg_processing_speed: 12.4,
        avg_faces_per_frame: 1.8,
        match_rate: 0.67
      }
    }
  }

  static async getContestantTimeline(contestantId: string, videoId?: string) {
    await delay(400)
    return {
      contestant_id: contestantId,
      timeline: [
        { frame: 150, timestamp: 5.0, confidence: 0.95 },
        { frame: 420, timestamp: 14.0, confidence: 0.87 },
        { frame: 890, timestamp: 29.7, confidence: 0.92 },
        { frame: 1250, timestamp: 41.7, confidence: 0.89 }
      ]
    }
  }

  // System status
  static async getSystemStatus() {
    await delay(200)
    return mockSystemStatus
  }

  // Health check
  static async healthCheck() {
    await delay(100)
    return { 
      status: 'connected', 
      data: { 
        timestamp: new Date().toISOString(),
        version: '2.0.0',
        mode: 'development'
      } 
    }
  }
}