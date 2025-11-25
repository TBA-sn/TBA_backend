# app/schemas/review.py
from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.schemas.common import Meta


class ExtensionRequest(BaseModel):
    user_id: int
    model_id: str
    code: str
    language: str
    trigger: str
    criteria: Optional[List[str]] = None

    meta: Meta = Field(default_factory=Meta)


class Snippet(BaseModel):
    code: str
    language: str
    file_path: str


class DetectionInfo(BaseModel):
    model_detected: Optional[str] = None
    confidence: Optional[float] = None


class EvaluationInfo(BaseModel):
    aspects: List[str] = Field(..., description="['bug','performance',...]")
    mode: Literal["sync", "async"] = "sync"


class CodeAnalysisRequestBody(BaseModel):
    user_id: int
    snippet: Snippet
    detection: Optional[DetectionInfo] = None
    evaluation: EvaluationInfo
    trigger: Literal["manual", "push", "PR"] = "manual"


class CodeAnalysisRequest(BaseModel):
    meta: Meta
    request: CodeAnalysisRequestBody


class LLMRequest(BaseModel):
    code: str
    language: str | None = None
    model: str | None = None
    criteria: List[str] = []


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


class ReviewDeleteRequestBody(BaseModel):
    user_id: int
    scope: Literal["single", "all"]
    review_id: Optional[int] = None


class ReviewDeleteRequest(BaseModel):
    meta: Meta
    request: ReviewDeleteRequestBody


class ReviewDeleteResponse(BaseModel):
    meta: Meta
    response: dict


class MetricsRequestBody(BaseModel):
    user_id: int
    group_by: Literal["day", "week", "month"] = "day"
    metrics: List[str] = ["global_score_avg", "model_score_avg"]


class MetricsRequest(BaseModel):
    meta: Meta
    request: MetricsRequestBody


class MetricsPoint(BaseModel):
    date: str
    global_score_avg: float
    model_score_avg: float


class MetricsResponseBody(BaseModel):
    series: List[MetricsPoint]


class MetricsResponse(BaseModel):
    meta: Meta
    response: MetricsResponseBody


class ReviewOut(BaseModel):
    id: int
    user_id: int
    model_id: str
    trigger: str
    status: str
    global_score: Optional[float] = None
    model_score: Optional[float] = None
    summary: str = ""
    created_at: datetime

    class Config:
        orm_mode = True


class LogCreate(BaseModel):
    user_id: int
    review_id: int
    action: str
    meta: Meta


# ===== (구) 단순 신규성 체크 버전 =====
class ReviewCheckRequest(BaseModel):
    user_id: int
    code: str
    language: str
    file_path: str


class ReviewCheckResponse(BaseModel):
    is_new: bool
    reason: str
    last_review_id: Optional[int] = None


class ReviewSnippet(BaseModel):
    code: str
    language: str
    file_path: str | None = None


class ReviewEvaluation(BaseModel):
    aspects: List[str]


class ReviewRequestBody(BaseModel):
    user_id: int
    snippet: Snippet
    trigger: Literal["manual", "auto"] = "manual"


class ReviewCreateEnvelope(BaseModel):
    meta: Meta
    request: ReviewRequestBody


class LLMAnalysisRequest(BaseModel):
    code: str
    language: str
    aspect: str


class LLMAnalysisResponse(BaseModel):
    aspect: str
    score: int
    comment: str
    model: str | None = None


class LLMCallbackBody(BaseModel):
    review_id: int
    aspect: str
    score: int
    comment: str
    model: str


# ====== (구) 카테고리 리스트 기반 – categories 배열 제거 버전 ======
class ReviewCategoryResult(BaseModel):
    name: str
    score: int
    comment: str


class ReviewScores(BaseModel):
    global_score: int
    model_score: int


class ReviewResultRecord(BaseModel):
    # 옛 구조와의 호환을 위해 남겨두지만,
    # categories 배열은 제거하고 카테고리별 점수/코멘트 필드로 분리
    user_id: str
    model: str
    trigger: str
    scores: ReviewScores

    score_bug: int
    score_maintainability: int
    score_style: int
    score_security: int

    comment_bug: Optional[str] = None
    comment_maintainability: Optional[str] = None
    comment_style: Optional[str] = None
    comment_security: Optional[str] = None

    summary: str
    status: str


class ReviewResultPatch(BaseModel):
    record: ReviewResultRecord


class ReviewListItem(BaseModel):
    review_id: str
    global_score: int
    model_score: int
    summary: str
    trigger: str
    status: str
    created_at: datetime


class ReviewListResponse(BaseModel):
    items: List[ReviewListItem]


class ReviewDetailResponse(BaseModel):
    # 옛 Response 예시용 – categories 배열 제거
    review_id: str
    global_score: int
    model_score: int
    summary: str
    trigger: str
    status: str
    created_at: datetime

    score_bug: int
    score_maintainability: int
    score_style: int
    score_security: int

    comment_bug: Optional[str] = None
    comment_maintainability: Optional[str] = None
    comment_style: Optional[str] = None
    comment_security: Optional[str] = None


# ====== (신) Meta 포함 신규성 체크 / 요청 / 결과 스펙 ======
class ReviewCheckBody(BaseModel):
    user_id: int
    code: str
    language: str
    file_path: str


class ReviewCheckRequest(BaseModel):
    meta: Meta
    body: ReviewCheckBody


class ReviewCheckResponseBody(BaseModel):
    is_new: bool
    reason: Literal["no_recent_review", "same_code", "recent_review"]
    last_review_id: Optional[int] = None


class ReviewCheckResponse(BaseModel):
    meta: Meta
    body: ReviewCheckResponseBody


class ReviewRequest(BaseModel):
    meta: Meta
    body: ReviewRequestBody


class ReviewRequestResponseBody(BaseModel):
    review_id: int
    status: Literal["pending", "processing", "done", "error"]


class ReviewRequestResponse(BaseModel):
    meta: Meta
    body: ReviewRequestResponseBody


class ReviewResultScores(BaseModel):
    # aspect_scores 대신 전역 점수 + 효율지수만 유지
    global_score: int
    model_score: int
    efficiency_index: float


class ReviewCategoryResult(BaseModel):
    # 유지하지만 더 이상 리스트로 묶어 쓰지 않음 (하단 Record에서도 배열 제거)
    name: str
    score: int
    comment: str


class ReviewResultRecord(BaseModel):
    """
    /v1/reviews/{review_id}/result PATCH 에서 쓰는 payload
    categories 배열을 날리고 카테고리별 점수/코멘트를 전부 필드로 쪼갠 구조
    """
    review_id: int
    user_id: int
    model: str
    trigger: str
    scores: ReviewResultScores  # global_score, model_score, efficiency_index

    # ===== 카테고리별 점수/코멘트 – 배열 대신 개별 필드 =====
    score_bug: int
    score_maintainability: int
    score_style: int
    score_security: int

    comment_bug: Optional[str] = None
    comment_maintainability: Optional[str] = None
    comment_style: Optional[str] = None
    comment_security: Optional[str] = None

    summary: str
    status: str


class ReviewResultMeta(BaseModel):
    version: str = "v1"
    ts: str
    correlation_id: str
    actor: str


class ReviewResultRequest(BaseModel):
    meta: ReviewResultMeta
    record: ReviewResultRecord


class ReviewListFilter(BaseModel):
    language: Optional[str] = None


class ReviewListRequestBody(BaseModel):
    user_id: int
    filters: ReviewListFilter
    page: int = 1


class ReviewListRequest(BaseModel):
    meta: ReviewResultMeta
    request: ReviewListRequestBody


class ReviewListItem(BaseModel):
    review_id: int
    global_score: Optional[int]
    model_score: Optional[int]
    efficiency_index: Optional[float]
    summary: Optional[str]
    trigger: str
    status: str
    created_at: str


class ReviewListResponseBody(BaseModel):
    items: list[ReviewListItem]


class ReviewListResponse(BaseModel):
    meta: ReviewResultMeta
    response: ReviewListResponseBody


class ReviewDetailCategory(BaseModel):
    """
    참고용으로 남겨두지만,
    실제 ResponseBody에는 categories 리스트를 더 이상 포함하지 않음.
    """
    name: str
    score: int
    comment: str


class ReviewDetailResponseBody(BaseModel):
    """
    /v1/reviews/{review_id} 상세 Response

    기존:
      categories: [ { name, score, comment }, ... ]  ❌

    변경:
      score_* / comment_* 필드로 전부 쪼갬 ✅
    """
    review_id: int
    global_score: Optional[int]
    model_score: Optional[int]
    efficiency_index: Optional[float]
    summary: Optional[str]
    trigger: str
    status: str
    created_at: str

    # 카테고리별 점수
    score_bug: Optional[int] = None
    score_maintainability: Optional[int] = None
    score_style: Optional[int] = None
    score_security: Optional[int] = None

    # 카테고리별 코멘트
    comment_bug: Optional[str] = None
    comment_maintainability: Optional[str] = None
    comment_style: Optional[str] = None
    comment_security: Optional[str] = None


class ReviewDetailResponse(BaseModel):
    meta: ReviewResultMeta
    response: ReviewDetailResponseBody


# ===== /api/v1/review 간단 버전 =====
class ReviewAPIRequest(BaseModel):
    code_snippet: str


class ReviewAPIResponse(BaseModel):
    quality_score: float
    review_summary: str
    scores_by_category: Dict[str, float]
    review_details: List[LLMReviewDetail]


# ===== 새 LLM 결과 포맷 (scores_by_category를 타입으로 고정) =====
class ReviewDetailItem(BaseModel):
    """
    한 개의 이슈(버그/성능/스타일 등)에 대한 상세 정보.
    LLM이 세부 이슈를 쏴줄 때 사용.
    """
    issue_id: Optional[str] = None
    issue_category: Category
    issue_severity: IssueSeverity
    issue_summary: str
    issue_details: Optional[str] = None
    issue_line_number: Optional[int] = None
    issue_column_number: Optional[int] = None


class ScoresByCategory(BaseModel):
    """
    8개 카테고리별 점수. 안 온 건 0으로 기본값 처리.
    """
    bug: int = 0
    maintainability: int = 0
    style: int = 0
    security: int = 0


class LLMQualityResponse(BaseModel):
    quality_score: int
    review_summary: str
    scores_by_category: ScoresByCategory
    # 카테고리 이름 -> 요약 코멘트
    review_details: Dict[str, str]


# ===== DB -> 응답 매핑용 =====
class ReviewItem(BaseModel):
    id: int
    user_id: int
    model: str
    trigger: str
    language: Optional[str] = None

    quality_score: int
    summary: str

    score_bug: int
    score_maintainability: int
    score_style: int
    score_security: int

    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewWithDetails(BaseModel):
    review: ReviewItem
    scores_by_category: ScoresByCategory
    review_details: List[ReviewDetailItem]
