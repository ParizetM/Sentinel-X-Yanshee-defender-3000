"""Routeur WebSocket pour flux temps réel (KAN-34)."""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket_manager import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket pour recevoir en direct les alertes et données capteurs."""
    await ws_manager.connect(websocket)
    try:
        # Envoi d'un message de bienvenue
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "message": "Connecté au flux temps réel Sentinel-X"
        })

        # Maintien de la connexion et écoute des pings/messages du client
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
