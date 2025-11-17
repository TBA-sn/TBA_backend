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
    Float,
)
from sqlalchemy.sql import func

from app.utils.database import Base


class Review(Base):
    __tablename__ = "review"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)

    # 코드 메타
    language = Column(String(50), nullable=False)
    file_path = Column(String(255), nullable=False)
    code = Column(Text, nullable=False)

    # 식별/트리거 정보
    code_fingerprint = Column(String(128), index=True)   # sha256(code)
    trigger = Column(String(20), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="pending")

    # 점수 요약(숫자 컬럼 – 필요하면 사용)
    global_score = Column(Integer, nullable=True)
    model_score = Column(Integer, nullable=True)
    efficiency_index = Column(Float, nullable=True)

    # 한 줄 요약
    summary = Column(Text, nullable=True)

    # 🔥 상세 JSON 컬럼들 (LLM 결과 전체 저장)
    #   - scores: { global_score, model_score, efficiency_index } 같은 형태
    #   - categories: [{ name, score, comment }, ...]
    scores = Column(JSON, nullable=True)
    categories = Column(JSON, nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
