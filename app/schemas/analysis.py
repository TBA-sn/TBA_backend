# app/schemas/analysis.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================
# 1) /v1/analysis/llm/request  (새 스펙 기반)
# ============================================================

class LLMRequestInput(BaseModel):
    code: str
    language: str


class LLMSchema(BaseModel):
    type: str
    properties: Dict[str, Any]
    required: List[str]


class LLMAnalysisRequestBody(BaseModel):
    model: str
    input: LLMRequestInput
    # JSON에서는 키 이름이 "schema" 여야 해서 alias 사용
    output_schema: LLMSchema = Field(..., alias="schema")

    class Config:
        # 이름으로도, alias("schema")로도 받을 수 있게
        populate_by_name = True


class LLMAnalysisRequest(BaseModel):
    request: LLMAnalysisRequestBody


# ============================================================
# 2) /v1/analysis/llm/callback  (새 스펙 기반)
# ============================================================

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class LLMCallbackMeta(BaseModel):
    version: str = "v1"
    ts: str
    correlation_id: str
    actor: str


class LLMCallbackResponse(BaseModel):
    # 굳이 RootModel 안 쓰고, 그냥 Dict로 처리
    aspect_scores: Dict[str, int]
    rationales: Dict[str, str]
    usage: Usage


class LLMCallbackRequest(BaseModel):
    meta: LLMCallbackMeta
    response: LLMCallbackResponse


# ============================================================
# 3) 기존 LLM Router 코드 호환용 타입들
#    (app/routers/llm/__init__.py 에서 import 중)
# ============================================================

class AnalysisRequestIn(BaseModel):
    meta: Optional[Dict[str, Any]] = None
    request: Dict[str, Any]


class AnalysisRequestAck(BaseModel):
    meta: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class AnalysisCallbackIn(BaseModel):
    meta: Dict[str, Any]
    response: Dict[str, Any]


class AnalysisStoredOut(BaseModel):
    meta: Dict[str, Any]
    record: Dict[str, Any]
