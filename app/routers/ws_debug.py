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
        """
        연결된 모든 클라이언트에 JSON 메시지 전송
        """
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

    # 새 클라이언트 접속 브로드캐스트 (옵션)
    await ws_manager.broadcast({
        "type": "system",
        "event": "client_connected",
        "connections": len(ws_manager.active_connections),
    })

    try:
        while True:
            # 클라이언트가 보낸 텍스트 메시지 수신
            data = await websocket.receive_text()

            # 받은 메시지를 그대로 전체에게 에코
            await ws_manager.broadcast({
                "type": "debug_echo",
                "message": data,
            })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        # 접속 종료 알림 (옵션)
        await ws_manager.broadcast({
            "type": "system",
            "event": "client_disconnected",
            "connections": len(ws_manager.active_connections),
        })
    except Exception:
        ws_manager.disconnect(websocket)
