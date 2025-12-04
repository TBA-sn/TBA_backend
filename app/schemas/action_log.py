# app/schemas/action_log.py
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class ActionLogOut(BaseModel):
    id: int
    log_id: str
    user_id: int
    case_id: str
    action: str
    timestamp: datetime
    report_id: Optional[int]
    class Config:
        from_attributes = True

class ActionLogList(BaseModel):
    items: list[ActionLogOut]
