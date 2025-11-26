from typing import Any, Dict, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class ResultInfo(BaseModel):
    result_ref: Optional[str] = None
    error_message: Optional[str] = None


class Audit(BaseModel):
    created_at: datetime
    updated_at: datetime


class Meta(BaseModel):
    user_id: Optional[int] = None
    review_id: Optional[int] = None
    version: str = "v1"
    actor: str
    code_fingerprint: Optional[str] = None
    model: Optional[str] = None
    result: Optional[ResultInfo] = None
    audit: Optional[Audit] = None


class SimpleMeta(BaseModel):
    version: str = "v1"
    ts: datetime
    correlation_id: Optional[str] = None
    actor: str


class ErrorResponse(BaseModel):
    code: str = Field(..., description="에러 코드 식별자 (예: VALIDATION_ERROR, NOT_FOUND 등)")
    message: str = Field(..., description="사람이 읽을 수 있는 에러 메시지")
    detail: Optional[Dict[str, Any]] = Field(
        default=None,
        description="추가 디버깅 정보 (옵션)",
    )
