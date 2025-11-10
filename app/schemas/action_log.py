# app/schemas/action_log.py
from datetime import datetime
from pydantic import BaseModel

class ActionLogOut(BaseModel):
    id: int
    log_id: str
    user_id: int
    case_id: str
    action: str
    timestamp: datetime

    class Config:
        from_attributes = True  # SQLAlchemy 모델 -> Pydantic 변환

class ActionLogList(BaseModel):
    items: list[ActionLogOut]
