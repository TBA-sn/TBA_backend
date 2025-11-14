from typing import Any, Dict, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class Progress(BaseModel):
    status: Literal["pending", "processing", "done", "error"]
    next_step: Optional[int] = None


class ResultInfo(BaseModel):
    result_ref: Optional[str] = None
    error_message: Optional[str] = None


class Audit(BaseModel):
    created_at: datetime
    updated_at: datetime


class Meta(BaseModel):
    """
    기본 메타 정보 공통 스키마
    - 대부분의 meta + body 구조에서 meta로 사용
    """
    id: Optional[int] = None
    version: str = "v1"
    actor: str
    identity: Optional[Dict[str, Any]] = None
    model: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    progress: Optional[Progress] = None
    result: Optional[ResultInfo] = None
    audit: Optional[Audit] = None


class SimpleMeta(BaseModel):
    """
    콜백/리스트 응답 등에 쓰는 경량 메타
    - ts, correlation_id 중심
    """
    version: str = "v1"
    ts: datetime
    correlation_id: Optional[str] = None
    actor: str


class ErrorResponse(BaseModel):
    """
    공통 에러 응답 스키마
    - 여러 라우터에서 response_model=ErrorResponse 로 사용할 수 있음
    """
    code: str = Field(..., description="에러 코드 식별자 (예: VALIDATION_ERROR, NOT_FOUND 등)")
    message: str = Field(..., description="사람이 읽을 수 있는 에러 메시지")
    detail: Optional[Dict[str, Any]] = Field(
        default=None,
        description="추가 디버깅 정보 (옵션)",
    )
