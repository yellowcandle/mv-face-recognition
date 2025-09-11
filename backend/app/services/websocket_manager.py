"""
WebSocket connection manager for real-time communication.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from fastapi import WebSocket
import msgpack

from app.core.config import settings

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for real-time communication."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_info: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_info[websocket] = {
            "connected_at": asyncio.get_event_loop().time(),
            "processing_active": False
        }
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        if websocket in self.connection_info:
            del self.connection_info[websocket]
            
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_to_client(self, websocket: WebSocket, data: Dict[str, Any]):
        """Send data to a specific client."""
        try:
            if settings.USE_MESSAGEPACK:
                # Use MessagePack for efficient binary serialization
                packed_data = msgpack.packb(data)
                await websocket.send_bytes(packed_data)
            else:
                # Use JSON as fallback
                await websocket.send_json(data)
                
        except Exception as e:
            logger.error(f"Error sending data to client: {e}")
            await self.disconnect(websocket)
    
    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast data to all connected clients."""
        if not self.active_connections:
            return
            
        # Serialize data once
        if settings.USE_MESSAGEPACK:
            packed_data = msgpack.packb(data)
        else:
            json_data = json.dumps(data)
        
        # Send to all clients
        disconnected = []
        
        for websocket in self.active_connections:
            try:
                if settings.USE_MESSAGEPACK:
                    await websocket.send_bytes(packed_data)
                else:
                    await websocket.send_text(json_data)
                    
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def send_processing_update(self, websocket: WebSocket, frame_data: Dict[str, Any]):
        """Send optimized processing update to client."""
        try:
            # Optimize data structure for real-time streaming
            optimized_data = {
                "t": frame_data.get("timestamp", 0),  # abbreviated keys for efficiency
                "f": frame_data.get("frame_number", 0),
                "faces": [
                    {
                        "b": face.get("bbox", []),
                        "c": face.get("detection_confidence", 0),
                        "n": face.get("contestant_name"),
                        "r": face.get("recognition_confidence", 0),
                        "m": face.get("matched", False)
                    }
                    for face in frame_data.get("faces", [])
                ],
                "stats": {
                    "fps": frame_data.get("processing_fps", 0),
                    "total_faces": frame_data.get("total_faces_detected", 0),
                    "recognized": frame_data.get("total_faces_recognized", 0)
                }
            }
            
            await self.send_to_client(websocket, {
                "type": "processing_update",
                "data": optimized_data
            })
            
        except Exception as e:
            logger.error(f"Error sending processing update: {e}")
    
    async def send_frame_image(self, websocket: WebSocket, frame_bytes: bytes, frame_info: Dict):
        """Send frame image data efficiently."""
        try:
            # Send frame info first
            await self.send_to_client(websocket, {
                "type": "frame_info",
                "data": frame_info
            })
            
            # Send frame image as binary data
            await websocket.send_bytes(frame_bytes)
            
        except Exception as e:
            logger.error(f"Error sending frame image: {e}")
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
    
    def is_processing_active(self, websocket: WebSocket) -> bool:
        """Check if processing is active for a connection."""
        return self.connection_info.get(websocket, {}).get("processing_active", False)
    
    def set_processing_status(self, websocket: WebSocket, active: bool):
        """Set processing status for a connection."""
        if websocket in self.connection_info:
            self.connection_info[websocket]["processing_active"] = active