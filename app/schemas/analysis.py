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
    """
    {
      "request": {
        "model": "...",
        "input": { "code": "...", "language": "..." },
        "schema": { ... }
      }
    }
    """
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
    """
    기존 코드 호환용 입력 스키마.
    - 최소한으로 meta + request 두 필드 제공
    - 내부 구조는 Dict[str, Any]로 열어두고, 라우터 코드가
      자유롭게 키 꺼내서 쓰도록 둠.
    """
    meta: Optional[Dict[str, Any]] = None
    request: Dict[str, Any]


class AnalysisRequestAck(BaseModel):
    """
    LLM 요청 접수 ACK 응답용 (대략적인 형태, extra는 Dict로 열어둠)
    """
    meta: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class AnalysisCallbackIn(BaseModel):
    """
    LLM worker -> 서버 콜백 입력.
    기존 코드가 meta / response 구조를 기대할 확률이 높아서 그대로 둠.
    """
    meta: Dict[str, Any]
    response: Dict[str, Any]


class AnalysisStoredOut(BaseModel):
    """
    DB에 저장된 분석 결과를 꺼내서 반환할 때 쓰는 출력 모델.
    record 안에 실제 점수/코멘트 등이 들어가도록 Dict로 열어둔다.
    """
    meta: Dict[str, Any]
    record: Dict[str, Any]
