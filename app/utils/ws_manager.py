# app/utils/ws_manager.py
from typing import List
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # dict → json 문자열로 변환
        data = json.dumps(message, ensure_ascii=False)
        to_remove = []
        for conn in self.active_connections:
            try:
                await conn.send_text(data)
            except WebSocketDisconnect:
                to_remove.append(conn)
            except Exception:
                to_remove.append(conn)

        for conn in to_remove:
            self.disconnect(conn)


manager = ConnectionManager()

# 편하게 쓰려고 만든 helper
async def trace(event: str, step: int | None = None, payload: dict | None = None):
    msg = {
        "event": event,            # ex) "review_request_created"
        "step": step,              # ex) 1~6 단계 번호
        "payload": payload or {},  # 추가 데이터
    }
    await manager.broadcast(msg)
