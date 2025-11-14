# app/models/action_log.py
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.utils.database import Base

class ActionLog(Base):
    __tablename__ = "action_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=True)

    event_name = Column(String(64), index=True, nullable=False)
    properties = Column(JSON, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())
