# app/models/review.py
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    JSON,
    Float
)

from app.utils.database import Base
from sqlalchemy.sql import func

# app/models/review.py 예시
class Review(Base):
    __tablename__ = "review"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    language = Column(String(50), nullable=False)
    file_path = Column(String(255), nullable=False)
    code = Column(Text, nullable=False)

    # 새로 필요할 수 있는 컬럼들
    code_fingerprint = Column(String(128), index=True)   # sha256 해시
    trigger = Column(String(20), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="pending")

    global_score = Column(Integer, nullable=True)
    model_score = Column(Integer, nullable=True)
    efficiency_index = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
