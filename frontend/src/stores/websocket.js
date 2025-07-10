import { writable } from 'svelte/store';
// Note: MessagePack functionality disabled for demo mode
// import { decode as unpack } from '@msgpack/msgpack';

// WebSocket connection state
export const websocketStore = writable({
  connected: false,
  connecting: false,
  error: null,
  lastMessage: null
});

// Processing updates from WebSocket
export const processingUpdates = writable({
  frameData: null,
  stats: null,
  timestamp: 0
});

class WebSocketManager {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.isConnecting = false;
  }

  connect() {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    websocketStore.update(state => ({ ...state, connecting: true, error: null }));

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/realtime-processing`;
      
      this.ws = new WebSocket(wsUrl);
      this.setupEventListeners();
    } catch (error) {
      console.error('WebSocket connection error:', error);
      websocketStore.update(state => ({ 
        ...state, 
        connecting: false, 
        error: 'Failed to create WebSocket connection' 
      }));
      this.isConnecting = false;
    }
  }

  setupEventListeners() {
    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.isConnecting = false;
      this.reconnectAttempts = 0;
      
      websocketStore.update(state => ({
        ...state,
        connected: true,
        connecting: false,
        error: null
      }));
    };

    this.ws.onmessage = async (event) => {
      try {
        let data;
        
        // Handle JSON data (MessagePack disabled for demo mode)
        if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
          // Skip binary data in demo mode
          console.log('Binary data received but skipped in demo mode');
          return;
        } else {
          // JSON text data
          data = JSON.parse(event.data);
        }

        this.handleMessage(data);
        
        websocketStore.update(state => ({ ...state, lastMessage: data }));
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      this.isConnecting = false;
      
      websocketStore.update(state => ({
        ...state,
        connected: false,
        connecting: false
      }));

      // Attempt to reconnect if not manually closed
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.isConnecting = false;
      
      websocketStore.update(state => ({
        ...state,
        connecting: false,
        error: 'WebSocket connection error'
      }));
    };
  }

  handleMessage(data) {
    switch (data.type) {
      case 'frame_update':
      case 'processing_update':
        processingUpdates.update(state => ({
          ...state,
          frameData: data.data,
          timestamp: Date.now()
        }));
        break;

      case 'parameter_updated':
        console.log(`Parameter ${data.parameter} updated to ${data.value}`);
        break;

      case 'error':
        console.error('WebSocket error message:', data.message);
        websocketStore.update(state => ({ ...state, error: data.message }));
        break;

      default:
        console.log('Unknown message type:', data.type);
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      if (this.reconnectAttempts <= this.maxReconnectAttempts) {
        this.connect();
      }
    }, delay);
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  startProcessing(videoName, startTime = 0, endTime = null) {
    return this.send({
      type: 'start_processing',
      video_name: videoName,
      start_time: startTime,
      end_time: endTime
    });
  }

  updateParameter(parameter, value) {
    return this.send({
      type: 'parameter_update',
      parameter: parameter,
      value: value
    });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
      this.ws = null;
    }
  }
}

// Create global WebSocket manager instance
export const wsManager = new WebSocketManager();

// Extend the store with WebSocket methods
websocketStore.connect = () => wsManager.connect();
websocketStore.disconnect = () => wsManager.disconnect();
websocketStore.send = (data) => wsManager.send(data);
websocketStore.startProcessing = (videoName, startTime, endTime) => 
  wsManager.startProcessing(videoName, startTime, endTime);
websocketStore.updateParameter = (parameter, value) => 
  wsManager.updateParameter(parameter, value);