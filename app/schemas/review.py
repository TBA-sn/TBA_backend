# app/schemas/review.py
from datetime import datetime
from typing import List, Literal, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.schemas.common import Meta


# ======================================================================
# 1️⃣ Extension → /v1/reviews/request 본문
# ======================================================================

class ExtensionRequest(BaseModel):
    """
    VSCode 확장(또는 UI, 웹 등)에서 /v1/reviews/request로 보내는 본문.
    meta는 안 보내면 Meta()가 기본으로 들어가도록 한다.
    """
    user_id: int
    model_id: str
    code: str
    language: str
    trigger: str
    # 선택: 기준 목록. 없으면 서버에서 기본 criteria 사용.
    criteria: Optional[List[str]] = None

    # meta를 선택으로 두고, 안 들어오면 Meta() 기본 생성
    meta: Meta = Field(default_factory=Meta)


# ======================================================================
# 2️⃣ 코드 분석(추가적인 고급 API용) 스키마
# ======================================================================

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
    user_id: int                                    # 🔥 int
    snippet: Snippet
    detection: Optional[DetectionInfo] = None
    evaluation: EvaluationInfo
    trigger: Literal["manual", "push", "PR"] = "manual"


class CodeAnalysisRequest(BaseModel):
    meta: Meta
    request: CodeAnalysisRequestBody


# ======================================================================
# 3️⃣ LLM 요청/응답 (서비스 내부에서 사용)
# ======================================================================

class LLMRequest(BaseModel):
    """
    review_code() 서비스에 넘기는 LLM 요청 바디.
    """
    code: str
    model: str
    criteria: List[str]


class CategoryResult(BaseModel):
    name: Literal[
        "유지보수성",
        "가독성",
        "확장성",
        "유연성",
        "간결성",
        "재사용성",
        "테스트 용이성",
    ]
    score: float
    comment: str


class LLMResponse(BaseModel):
    scores: dict  # { "global": 82, "model": 76 }
    categories: List[CategoryResult]
    summary: str

# ======================================================================
# 9️⃣ 삭제 요청/응답
# ======================================================================

class ReviewDeleteRequestBody(BaseModel):
    user_id: int                                    # 🔥 int
    scope: Literal["single", "all"]
    review_id: Optional[int] = None                 # 🔥 int


class ReviewDeleteRequest(BaseModel):
    meta: Meta
    request: ReviewDeleteRequestBody


class ReviewDeleteResponse(BaseModel):
    meta: Meta
    response: dict  # { "deleted": 1 }


# ======================================================================
# 🔟 통계 조회
# ======================================================================

class MetricsRequestBody(BaseModel):
    user_id: int                                    # 🔥 int
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


# ======================================================================
# 🔁 /v1/reviews/request 응답용 (ORM → JSON 변환)
# ======================================================================

class ReviewOut(BaseModel):
    """
    /v1/reviews/request 의 response_model.
    """
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
    """
    ActionLog 생성 시 사용할 단순 DTO (필요하면 사용).
    """
    user_id: int
    review_id: int
    action: str
    meta: Meta

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

class ReviewCategoryResult(BaseModel):
    name: str
    score: int
    comment: str

class ReviewScores(BaseModel):
    global_score: int
    model_score: int

class ReviewResultRecord(BaseModel):
    user_id: str
    model: str
    trigger: str
    scores: ReviewScores
    categories: List[ReviewCategoryResult]
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
    review_id: str
    global_score: int
    model_score: int
    summary: str
    trigger: str
    status: str
    created_at: datetime
    categories: List[ReviewCategoryResult]

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
    aspect_scores: Dict[str, int]
    global_score: int
    model_score: int
    efficiency_index: float


class ReviewCategoryResult(BaseModel):
    name: str
    score: int
    comment: str


class ReviewResultRecord(BaseModel):
    review_id: str
    user_id: str
    model: str
    trigger: str
    scores: ReviewResultScores
    categories: list[ReviewCategoryResult]
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

    # app/schemas/review.py 에 추가

class ReviewListFilter(BaseModel):
    language: Optional[str] = None


class ReviewListRequestBody(BaseModel):
    user_id: int
    filters: ReviewListFilter
    page: int = 1


class ReviewListRequest(BaseModel):
    meta: ReviewResultMeta  # 동일 meta 타입 재사용
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
    name: str
    score: int
    comment: str


class ReviewDetailResponseBody(BaseModel):
    review_id: int
    global_score: Optional[int]
    model_score: Optional[int]
    efficiency_index: Optional[float]
    summary: Optional[str]
    trigger: str
    status: str
    created_at: str
    categories: list[ReviewDetailCategory]


class ReviewDetailResponse(BaseModel):
    meta: ReviewResultMeta
    response: ReviewDetailResponseBody
