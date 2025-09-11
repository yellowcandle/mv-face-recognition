"""
WebSocket endpoints for real-time updates.
"""

from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.job_subscribers: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        
        # Remove from job subscriptions
        for job_id, subscribers in self.job_subscribers.items():
            subscribers.discard(websocket)
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def subscribe_to_job(self, websocket: WebSocket, job_id: str):
        """Subscribe a connection to job updates."""
        if job_id not in self.job_subscribers:
            self.job_subscribers[job_id] = set()
        
        self.job_subscribers[job_id].add(websocket)
        logger.info(f"Subscribed to job {job_id}. Subscribers: {len(self.job_subscribers[job_id])}")
    
    async def unsubscribe_from_job(self, websocket: WebSocket, job_id: str):
        """Unsubscribe a connection from job updates."""
        if job_id in self.job_subscribers:
            self.job_subscribers[job_id].discard(websocket)
            
            # Clean up empty subscription lists
            if not self.job_subscribers[job_id]:
                del self.job_subscribers[job_id]
    
    async def send_to_connection(self, websocket: WebSocket, message: dict):
        """Send message to a specific connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send message to connection: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connections."""
        if not self.active_connections:
            return
        
        # Send to all connections
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send broadcast message: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_to_job_subscribers(self, job_id: str, message: dict):
        """Broadcast message to all subscribers of a specific job."""
        if job_id not in self.job_subscribers:
            return
        
        subscribers = self.job_subscribers[job_id].copy()
        disconnected = set()
        
        for connection in subscribers:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send job update: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

# Global connection manager
manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await handle_client_message(websocket, message)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error handling client message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Internal server error"
                }))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def handle_client_message(websocket: WebSocket, message: dict):
    """Handle incoming client messages."""
    message_type = message.get("type")
    
    if message_type == "subscribe":
        job_id = message.get("job_id")
        if job_id:
            await manager.subscribe_to_job(websocket, job_id)
            await websocket.send_text(json.dumps({
                "type": "subscribed",
                "job_id": job_id
            }))
    
    elif message_type == "unsubscribe":
        job_id = message.get("job_id")
        if job_id:
            await manager.unsubscribe_from_job(websocket, job_id)
            await websocket.send_text(json.dumps({
                "type": "unsubscribed",
                "job_id": job_id
            }))
    
    elif message_type == "ping":
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": message.get("timestamp")
        }))
    
    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        }))

# Functions for sending updates (to be called from services)

async def send_processing_progress(job_id: str, progress_data: dict):
    """Send processing progress update to job subscribers."""
    message = {
        "type": "processing_progress",
        "job_id": job_id,
        "data": progress_data
    }
    await manager.broadcast_to_job_subscribers(job_id, message)

async def send_processing_complete(job_id: str, result_data: dict):
    """Send processing completion notification."""
    message = {
        "type": "processing_complete",
        "job_id": job_id,
        "data": result_data
    }
    await manager.broadcast_to_job_subscribers(job_id, message)

async def send_processing_error(job_id: str, error_message: str):
    """Send processing error notification."""
    message = {
        "type": "processing_error",
        "job_id": job_id,
        "error": error_message
    }
    await manager.broadcast_to_job_subscribers(job_id, message)

async def send_system_status_update(status_data: dict):
    """Send system status update to all connections."""
    message = {
        "type": "system_status",
        "data": status_data
    }
    await manager.broadcast_to_all(message)

# Export manager for use in services
__all__ = ["manager", "send_processing_progress", "send_processing_complete", 
           "send_processing_error", "send_system_status_update"]