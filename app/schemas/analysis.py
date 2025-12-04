# app/schemas/analysis.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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
    output_schema: LLMSchema = Field(..., alias="schema")

    class Config:
        populate_by_name = True


class LLMAnalysisRequest(BaseModel):
    request: LLMAnalysisRequestBody


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class LLMCallbackMeta(BaseModel):
    version: str = "v1"
    ts: str
    correlation_id: str
    actor: str


class LLMCallbackResponse(BaseModel):
    aspect_scores: Dict[str, int]
    rationales: Dict[str, str]
    usage: Usage


class LLMCallbackRequest(BaseModel):
    meta: LLMCallbackMeta
    response: LLMCallbackResponse


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
