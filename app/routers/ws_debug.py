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
        모든 활성 WebSocket 클라이언트에게 message(dict)를 전송.
        """
        data = json.dumps(message, ensure_ascii=False, default=str)
        to_remove: list[WebSocket] = []

        for conn in self.active_connections:
            try:
                await conn.send_text(data)
            except Exception:
                # 끊긴 연결은 리스트에서 제거
                to_remove.append(conn)

        for conn in to_remove:
            self.disconnect(conn)


# 여기 이 인스턴스를 외부에서 import 해서 씀
ws_manager = WebSocketManager()


@router.websocket("/ws/debug")
async def ws_debug_endpoint(websocket: WebSocket):
    """
    프론트(브라우저)에서 ws://서버주소/ws/debug 로 연결하는 엔드포인트.
    """
    await ws_manager.connect(websocket)
    try:
        # 클라이언트에서 보내는 메시지는 안 써도 되지만
        # 연결을 유지하기 위해 그냥 무한히 receive 해줌
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
