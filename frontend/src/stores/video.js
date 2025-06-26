import { writable } from 'svelte/store';

// Video state management
export const videoStore = writable({
  availableVideos: [],
  selectedVideo: null,
  videoInfo: null,
  loading: false,
  error: null
});

class VideoManager {
  constructor() {
    this.apiBaseUrl = '/api';
  }

  async loadVideos() {
    videoStore.update(state => ({ ...state, loading: true, error: null }));

    try {
      const response = await fetch(`${this.apiBaseUrl}/videos/`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      videoStore.update(state => ({
        ...state,
        availableVideos: data.videos,
        loading: false
      }));

      return data.videos;
    } catch (error) {
      console.error('Error loading videos:', error);
      
      videoStore.update(state => ({
        ...state,
        loading: false,
        error: error.message
      }));
      
      return [];
    }
  }

  async selectVideo(videoName) {
    if (!videoName) return;

    videoStore.update(state => ({ ...state, loading: true, error: null }));

    try {
      const response = await fetch(`${this.apiBaseUrl}/videos/${encodeURIComponent(videoName)}`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const videoInfo = await response.json();
      
      videoStore.update(state => ({
        ...state,
        selectedVideo: videoName,
        videoInfo: videoInfo,
        loading: false
      }));

      return videoInfo;
    } catch (error) {
      console.error('Error selecting video:', error);
      
      videoStore.update(state => ({
        ...state,
        loading: false,
        error: error.message
      }));
      
      return null;
    }
  }

  async updateProcessingParameters(parameters) {
    try {
      const promises = Object.entries(parameters).map(([parameter, value]) =>
        fetch(`${this.apiBaseUrl}/processing/parameters`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ parameter, value })
        })
      );

      await Promise.all(promises);
      return true;
    } catch (error) {
      console.error('Error updating parameters:', error);
      return false;
    }
  }

  async startProcessing(videoName, startTime = 0, endTime = null) {
    try {
      const response = await fetch(`${this.apiBaseUrl}/processing/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_name: videoName,
          start_time: startTime,
          end_time: endTime
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error starting processing:', error);
      throw error;
    }
  }

  async stopProcessing() {
    try {
      const response = await fetch(`${this.apiBaseUrl}/processing/stop`, {
        method: 'POST'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return true;
    } catch (error) {
      console.error('Error stopping processing:', error);
      return false;
    }
  }
}

// Create global video manager instance
export const videoManager = new VideoManager();

// Extend stores with video manager methods
videoStore.loadVideos = () => videoManager.loadVideos();
videoStore.selectVideo = (videoName) => videoManager.selectVideo(videoName);
videoStore.updateParameters = (parameters) => videoManager.updateProcessingParameters(parameters);
videoStore.startProcessing = (videoName, startTime, endTime) => videoManager.startProcessing(videoName, startTime, endTime);
videoStore.stopProcessing = () => videoManager.stopProcessing();