"""WebSocket connection manager for handling multiple clients."""

import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("cinesync.ws")


class ConnectionManager:
    """Manages WebSocket connections with broadcast support."""

    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"New connection. Active: {self.active_count}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info(f"Connection removed. Active: {self.active_count}")

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def send_json(self, websocket: WebSocket, data: dict):
        """Send JSON to a specific client."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Send error: {e}")
            self.disconnect(websocket)

    async def broadcast(self, data: dict):
        """Broadcast JSON to all connected clients."""
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_bytes(self, data: bytes):
        """Broadcast binary data (audio chunks) to all clients."""
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_bytes(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)
