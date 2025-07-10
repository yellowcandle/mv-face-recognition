import { writable } from 'svelte/store';

// Processing state management
export const processingStore = writable({
  isProcessing: false,
  currentFrame: 0,
  totalFrames: 0,
  processingFps: 0,
  startTime: 0,
  endTime: null,
  parameters: {
    detection_threshold: 0.5,
    similarity_threshold: 0.15,
    frame_skip: 5
  },
  statistics: {
    totalFacesDetected: 0,
    totalFacesRecognized: 0,
    processingTime: 0,
    averageConfidence: 0
  },
  error: null
});

// Real-time processing results
export const resultsStore = writable({
  currentFrameResults: [],
  allResults: [],
  contestantAppearances: {},
  statistics: {
    totalFacesDetected: 0,
    totalFacesRecognized: 0,
    processingTime: 0
  }
});

class ProcessingManager {
  constructor() {
    this.processingActive = false;
    this.currentStats = {
      totalFacesDetected: 0,
      totalFacesRecognized: 0,
      processingTime: 0
    };
  }

  startProcessing(videoName, startTime = 0, endTime = null) {
    processingStore.update(state => ({
      ...state,
      isProcessing: true,
      startTime,
      endTime,
      currentFrame: 0,
      error: null
    }));

    // Reset results
    resultsStore.update(state => ({
      ...state,
      currentFrameResults: [],
      allResults: [],
      contestantAppearances: {},
      statistics: {
        totalFacesDetected: 0,
        totalFacesRecognized: 0,
        processingTime: 0
      }
    }));

    this.processingActive = true;
  }

  stopProcessing() {
    processingStore.update(state => ({
      ...state,
      isProcessing: false
    }));

    this.processingActive = false;
  }

  updateParameters(parameters) {
    processingStore.update(state => ({
      ...state,
      parameters: { ...state.parameters, ...parameters }
    }));
  }

  updateProcessingStats(frameData) {
    if (!frameData) return;

    // Update processing store
    processingStore.update(state => ({
      ...state,
      currentFrame: frameData.f || frameData.frame_number || state.currentFrame,
      processingFps: frameData.stats?.fps || state.processingFps,
      statistics: {
        ...state.statistics,
        totalFacesDetected: frameData.stats?.total_faces || state.statistics.totalFacesDetected,
        totalFacesRecognized: frameData.stats?.recognized || state.statistics.totalFacesRecognized,
        processingTime: frameData.stats?.processing_time || state.statistics.processingTime
      }
    }));

    // Update results store
    resultsStore.update(state => {
      const newState = { ...state };
      
      // Update current frame results
      newState.currentFrameResults = frameData.faces || [];
      
      // Add to all results
      newState.allResults.push({
        frameNumber: frameData.f || frameData.frame_number,
        timestamp: frameData.t || frameData.timestamp,
        faces: frameData.faces || []
      });

      // Update contestant appearances
      if (frameData.faces) {
        frameData.faces.forEach(face => {
          if ((face.m || face.matched) && (face.n || face.contestant_name)) {
            const name = face.n || face.contestant_name;
            
            if (!newState.contestantAppearances[name]) {
              newState.contestantAppearances[name] = {
                totalAppearances: 0,
                maxConfidence: 0,
                avgConfidence: 0,
                confidenceScores: [],
                firstAppearance: frameData.f || frameData.frame_number,
                lastAppearance: frameData.f || frameData.frame_number
              };
            }
            
            const appearance = newState.contestantAppearances[name];
            const confidence = face.r || face.recognition_confidence || 0;
            
            appearance.totalAppearances++;
            appearance.confidenceScores.push(confidence);
            appearance.maxConfidence = Math.max(appearance.maxConfidence, confidence);
            appearance.avgConfidence = appearance.confidenceScores.reduce((a, b) => a + b, 0) / appearance.confidenceScores.length;
            appearance.lastAppearance = frameData.f || frameData.frame_number;
          }
        });
      }

      // Update global statistics
      if (frameData.stats) {
        newState.statistics = {
          totalFacesDetected: frameData.stats.total_faces || frameData.stats.totalFacesDetected || 0,
          totalFacesRecognized: frameData.stats.recognized || frameData.stats.totalFacesRecognized || 0,
          processingTime: frameData.stats.processing_time || 0
        };
      }

      return newState;
    });
  }

  setError(error) {
    processingStore.update(state => ({
      ...state,
      error: error.message || error,
      isProcessing: false
    }));
  }

  clearError() {
    processingStore.update(state => ({
      ...state,
      error: null
    }));
  }

  getContestantRanking() {
    let ranking = [];
    
    resultsStore.subscribe(state => {
      ranking = Object.entries(state.contestantAppearances)
        .map(([name, data]) => ({
          name,
          totalAppearances: data.totalAppearances,
          avgConfidence: data.avgConfidence,
          maxConfidence: data.maxConfidence,
          score: data.totalAppearances * data.avgConfidence // Combined score
        }))
        .sort((a, b) => b.score - a.score);
    })();

    return ranking;
  }

  exportResults(format = 'json') {
    let results = null;
    
    resultsStore.subscribe(state => {
      results = state;
    })();

    if (format === 'csv') {
      return this.exportToCSV(results);
    } else {
      return this.exportToJSON(results);
    }
  }

  exportToJSON(results) {
    const exportData = {
      metadata: {
        exportTime: new Date().toISOString(),
        totalFrames: results.allResults.length,
        totalFacesDetected: results.statistics.totalFacesDetected,
        totalFacesRecognized: results.statistics.totalFacesRecognized
      },
      frameResults: results.allResults,
      contestantAppearances: results.contestantAppearances,
      statistics: results.statistics
    };

    return JSON.stringify(exportData, null, 2);
  }

  exportToCSV(results) {
    const headers = [
      'Frame Number',
      'Timestamp',
      'Faces Count',
      'Recognized Faces',
      'Contestant Names',
      'Average Confidence'
    ];

    const rows = results.allResults.map(frame => {
      const recognizedFaces = (frame.faces || []).filter(face => face.m || face.matched);
      const names = recognizedFaces.map(face => face.n || face.contestant_name).join(';');
      const avgConfidence = recognizedFaces.length > 0 
        ? recognizedFaces.reduce((sum, face) => sum + (face.r || face.recognition_confidence || 0), 0) / recognizedFaces.length
        : 0;

      return [
        frame.frameNumber,
        frame.timestamp.toFixed(2),
        frame.faces.length,
        recognizedFaces.length,
        names,
        avgConfidence.toFixed(3)
      ];
    });

    const csvContent = [headers, ...rows]
      .map(row => row.join(','))
      .join('\n');

    return csvContent;
  }
}

// Create global processing manager instance
export const processingManager = new ProcessingManager();

// Extend stores with processing manager methods
processingStore.start = (videoName, startTime, endTime) => 
  processingManager.startProcessing(videoName, startTime, endTime);
processingStore.stop = () => processingManager.stopProcessing();
processingStore.updateParameters = (parameters) => processingManager.updateParameters(parameters);
processingStore.updateStats = (frameData) => processingManager.updateProcessingStats(frameData);
processingStore.setError = (error) => processingManager.setError(error);
processingStore.clearError = () => processingManager.clearError();

resultsStore.getRanking = () => processingManager.getContestantRanking();
resultsStore.export = (format) => processingManager.exportResults(format);