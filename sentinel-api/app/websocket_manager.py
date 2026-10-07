"""Gestionnaire de connexions WebSocket pour la diffusion temps réel (KAN-34)."""

import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("sentinel.ws")


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Nouveau client WebSocket connecté. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client WebSocket déconnecté. Restants: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Diffuse un message JSON à tous les clients connectés."""
        if not self.active_connections:
            return

        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Erreur envoi WebSocket vers un client: {e}")
                self.disconnect(connection)


ws_manager = WebSocketManager()
