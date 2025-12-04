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
    meta: Meta
    body: ReviewRequestBody


class ReviewRequestResponseBody(BaseModel):
    review_id: int


class ReviewRequestResponse(BaseModel):
    meta: Meta
    body: ReviewRequestResponseBody


# ─────────────────────────────────────────
# LLM 요청/응답 타입 (서비스/라우터에서 공통 사용)
# ─────────────────────────────────────────

class ScoresByCategory(BaseModel):
    bug: int = 0
    maintainability: int = 0
    style: int = 0
    security: int = 0


class LLMRequest(BaseModel):
    code: str
    language: Optional[str] = None
    model: Optional[str] = None
    criteria: List[str] = Field(default_factory=list)


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
    issue_category: str
    issue_severity: IssueSeverity
    issue_summary: str
    issue_details: str
    issue_line_number: int
    issue_column_number: Optional[int] = None


class LLMResponse(BaseModel):
    quality_score: float
    review_summary: str
    scores_by_category: Dict[str, float]
    review_details: List[LLMReviewDetail]


class LLMQualityResponse(BaseModel):
    quality_score: int
    review_summary: str
    scores_by_category: ScoresByCategory
    review_details: Dict[str, str]


# ─────────────────────────────────────────
# GET /v1/reviews/{review_id}
# ─────────────────────────────────────────

class ReviewResultBody(BaseModel):
    quality_score: int
    summary: str
    scores_by_category: ScoresByCategory
    comments: Dict[str, str]


class ReviewDetailResponse(BaseModel):
    meta: Meta
    body: ReviewResultBody


class ReviewAPIRequest(BaseModel):
    code_snippet: str


class ReviewAPIResponse(BaseModel):
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

class FixRequest(BaseModel):
    review_id: int
    code: str


class FixResponseBody(BaseModel):
    code: str
    summary: str
    comments: Dict[str, str]