# app/routers/ws.py
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["ws"])


class ConnectionManager:
    def __init__(self) -> None:
        # user_id 별로 여러 연결 관리
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        conns = self.active_connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, message: dict):
        conns = self.active_connections.get(user_id, [])
        for ws in conns:
            await ws.send_json(message)


ws_manager = ConnectionManager()


@router.websocket("/reviews/{user_id}")
async def reviews_ws(websocket: WebSocket, user_id: int):
    """
    클라이언트(Extension/Web)가 user_id 기준으로 붙는 채널.
    - 클라는 ws://host/ws/reviews/1 이런 식으로 연결
    - 서버는 리뷰 완료/에러 시 이 채널로 이벤트 push
    """
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            # 클라에서 뭔가 보내고 싶으면 여기서 받으면 됨
            _ = await websocket.receive_text()
            # 지금은 단순 알림용이니까 그냥 무시
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
