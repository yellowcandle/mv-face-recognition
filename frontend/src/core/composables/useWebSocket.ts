import { ref, onMounted, onUnmounted } from 'vue'
import type { WebSocketMessage } from '@/core/types/api'

export function useWebSocket() {
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 2000
  
  let socket: WebSocket | null = null
  let reconnectTimer: number | null = null
  
  // Event handlers
  const messageHandlers = new Map<string, Set<(data: any) => void>>()
  const connectionHandlers = new Set<(connected: boolean) => void>()
  
  const connect = () => {
    try {
      const wsUrl = import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000'
      socket = new WebSocket(`${wsUrl}/ws`)
      
      socket.onopen = () => {
        isConnected.value = true
        reconnectAttempts.value = 0
        console.log('WebSocket connected')
        
        // Notify connection handlers
        connectionHandlers.forEach(handler => handler(true))
      }
      
      socket.onclose = () => {
        isConnected.value = false
        console.log('WebSocket disconnected')
        
        // Notify connection handlers
        connectionHandlers.forEach(handler => handler(false))
        
        // Attempt reconnection
        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++
          console.log(`Reconnecting... Attempt ${reconnectAttempts.value}`)
          
          reconnectTimer = window.setTimeout(() => {
            connect()
          }, reconnectDelay * reconnectAttempts.value)
        }
      }
      
      socket.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
      
      socket.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          
          // Handle message based on type
          const handlers = messageHandlers.get(message.type)
          if (handlers) {
            handlers.forEach(handler => {
              try {
                handler(message.data || message)
              } catch (error) {
                console.error('Error in message handler:', error)
              }
            })
          }
          
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }
      
    } catch (error) {
      console.error('Error connecting to WebSocket:', error)
    }
  }
  
  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    
    if (socket) {
      socket.close()
      socket = null
    }
    
    isConnected.value = false
  }
  
  const send = (message: object) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message))
      return true
    }
    return false
  }
  
  // Subscribe to specific job updates
  const subscribeToJob = (jobId: string) => {
    send({
      type: 'subscribe',
      job_id: jobId
    })
  }
  
  const unsubscribeFromJob = (jobId: string) => {
    send({
      type: 'unsubscribe',
      job_id: jobId
    })
  }
  
  // Event listener management
  const on = (eventType: string, handler: (data: any) => void) => {
    if (!messageHandlers.has(eventType)) {
      messageHandlers.set(eventType, new Set())
    }
    messageHandlers.get(eventType)!.add(handler)
    
    // Return unsubscribe function
    return () => {
      const handlers = messageHandlers.get(eventType)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          messageHandlers.delete(eventType)
        }
      }
    }
  }
  
  const onConnection = (handler: (connected: boolean) => void) => {
    connectionHandlers.add(handler)
    
    // Return unsubscribe function
    return () => {
      connectionHandlers.delete(handler)
    }
  }
  
  // Ping to keep connection alive
  const ping = () => {
    if (isConnected.value) {
      send({
        type: 'ping',
        timestamp: new Date().toISOString()
      })
    }
  }
  
  // Auto-connect on mount (only in production or when explicitly enabled)
  onMounted(() => {
    const shouldConnect = import.meta.env.PROD || import.meta.env.VITE_ENABLE_WEBSOCKET === 'true'
    
    if (shouldConnect) {
      connect()
      
      // Set up ping interval
      const pingInterval = setInterval(ping, 30000) // Ping every 30 seconds
      
      onUnmounted(() => {
        clearInterval(pingInterval)
        disconnect()
      })
    } else {
      console.log('WebSocket disabled in development mode')
    }
  })
  
  return {
    // State
    isConnected,
    reconnectAttempts,
    
    // Methods
    connect,
    disconnect,
    send,
    subscribeToJob,
    unsubscribeFromJob,
    on,
    onConnection,
    ping
  }
}