# app/routers/ws_debug.py
from typing import List
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["ws-debug"])


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        data = json.dumps(message, ensure_ascii=False, default=str)
        to_remove: list[WebSocket] = []

        for conn in self.active_connections:
            try:
                await conn.send_text(data)
            except Exception:
                to_remove.append(conn)

        for conn in to_remove:
            self.disconnect(conn)


ws_manager = WebSocketManager()


@router.websocket("/ws/debug")
async def ws_debug_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)

    await ws_manager.broadcast({
        "type": "system",
        "event": "client_connected",
        "connections": len(ws_manager.active_connections),
    })

    try:
        while True:
            data = await websocket.receive_text()

            await ws_manager.broadcast({
                "type": "debug_echo",
                "message": data,
            })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        await ws_manager.broadcast({
            "type": "system",
            "event": "client_disconnected",
            "connections": len(ws_manager.active_connections),
        })
    except Exception:
        ws_manager.disconnect(websocket)
