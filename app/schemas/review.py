from typing import List, Optional, Dict

from pydantic import BaseModel, Field

from app.schemas.common import Meta


# ─────────────────────────────────────────
# 공통: 코드 조각
# ─────────────────────────────────────────

class Snippet(BaseModel):
    code: str


# ─────────────────────────────────────────
# POST /v1/reviews/request
# ─────────────────────────────────────────

class ReviewRequestBody(BaseModel):
    snippet: Snippet


class ReviewRequest(BaseModel):
    """
    POST /v1/reviews/request 요청 바디

    {
      "meta": { ... Meta ... },
      "body": {
        "snippet": { "code": "..." }
      }
    }
    """
    meta: Meta
    body: ReviewRequestBody


class ReviewRequestResponseBody(BaseModel):
    """
    POST /v1/reviews/request 응답 body

    {
      "review_id": 123
    }
    """
    review_id: int


class ReviewRequestResponse(BaseModel):
    """
    {
      "meta": { ... Meta ... },
      "body": { "review_id": 123 }
    }
    """
    meta: Meta
    body: ReviewRequestResponseBody


# ─────────────────────────────────────────
# LLM 요청/응답 타입 (서비스/라우터에서 공통 사용)
# ─────────────────────────────────────────

class ScoresByCategory(BaseModel):
    """
    LLM / DB / 응답 공통으로 쓰는 카테고리 점수 구조
    """
    bug: int = 0
    maintainability: int = 0
    style: int = 0
    security: int = 0


class LLMRequest(BaseModel):
    """
    app.services.llm_client.review_code() 에 넘기는 요청 타입
    """
    code: str
    language: Optional[str] = None
    model: Optional[str] = None
    criteria: List[str] = Field(default_factory=list)


# ===== /api/v1/review 간단 버전에서 쓰는 디테일 구조 =====

from enum import Enum


class IssueSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Category(str, Enum):
    BUG = "Bug"
    MAINTAINABILITY = "Maintainability"
    STYLE = "Style"
    SECURITY = "Security"


class LLMReviewDetail(BaseModel):
    issue_id: str
    issue_category: str          # 또는 Category 로 바꿔도 됨 (기존 코드 기준 맞추기)
    issue_severity: IssueSeverity
    issue_summary: str
    issue_details: str
    issue_line_number: int
    issue_column_number: Optional[int] = None


class LLMResponse(BaseModel):
    """
    옛날 generic LLM 응답 (review_api 등에서 쓸 수 있음)
    """
    quality_score: float
    review_summary: str
    scores_by_category: Dict[str, float]
    review_details: List[LLMReviewDetail]


# ===== 새로운 LLM 품질 응답 (v1/reviews에서 사용) =====

class LLMQualityResponse(BaseModel):
    """
    v1/reviews 파이프라인에서 사용하는 LLM 결과 타입
    """
    quality_score: int
    review_summary: str
    scores_by_category: ScoresByCategory
    # 카테고리 이름 -> 요약 코멘트
    review_details: Dict[str, str]


# ─────────────────────────────────────────
# GET /v1/reviews/{review_id}
# ─────────────────────────────────────────

class ReviewResultBody(BaseModel):
    """
    /v1/reviews/{review_id} 의 body 부분

    {
      "quality_score": 96,
      "summary": "...",
      "scores_by_category": { ... },
      "comments": { ... }
    }
    """
    quality_score: int
    summary: str
    scores_by_category: ScoresByCategory
    comments: Dict[str, str]


class ReviewDetailResponse(BaseModel):
    """
    /v1/reviews/{review_id} 최종 응답

    {
      "meta": { ... Meta ... },
      "body": {
        "quality_score": ...,
        "summary": "...",
        "scores_by_category": { ... },
        "comments": { ... }
      }
    }
    """
    meta: Meta
    body: ReviewResultBody


# ─────────────────────────────────────────
# /api/v1/review (간단 버전) – review_api.py에서 사용
# ─────────────────────────────────────────

class ReviewAPIRequest(BaseModel):
    """
    /api/v1/review 요청

    {
      "code_snippet": "..."
    }
    """
    code_snippet: str


class ReviewAPIResponse(BaseModel):
    """
    /api/v1/review 응답

    {
      "quality_score": ...,
      "review_summary": "...",
      "scores_by_category": {
        "bug": ...,
        "maintainability": ...,
        "style": ...,
        "security": ...
      },
      "review_details": [ ... LLMReviewDetail ... ]
    }
    """
    quality_score: float
    review_summary: str
    scores_by_category: Dict[str, float]
    review_details: List[LLMReviewDetail]


# ─────────────────────────────────────────
# 리뷰 목록용 스키마
# ─────────────────────────────────────────

class ReviewListItem(BaseModel):
    review_id: int
    github_id: Optional[str] = None
    model: str
    trigger: Optional[str] = None
    language: Optional[str] = None
    quality_score: int
    summary: str
    scores_by_category: ScoresByCategory
    comments: Dict[str, str]
    audit: str


class ReviewListResponse(BaseModel):
    meta: Meta
    body: List[ReviewListItem]