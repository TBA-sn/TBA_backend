from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

class ReviewCaseBrief(BaseModel):
    review_id: int
    category: Optional[str] = None  # 결과 안에 카테고리명 있으면 뽑아 매핑

class ReviewReportCreate(BaseModel):
    model_id: str
    # 생성 직후엔 summary/score는 없음

class ReviewReportOut(BaseModel):
    id: int
    user_id: int
    model_id: str
    summary: Optional[str]
    global_score: Optional[int]
    model_score: Optional[int]
    created_at: datetime
    reviews: List[ReviewCaseBrief] = []

    class Config:
        from_attributes = True

class ReviewReportFinalizeOut(BaseModel):
    id: int
    summary: str
    global_score: int
    model_score: int
