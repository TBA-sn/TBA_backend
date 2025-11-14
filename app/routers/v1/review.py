# app/routers/v1/review.py
from uuid import uuid4
import hashlib 
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_

from app.utils.database import get_session
from app.schemas.common import Meta, ErrorResponse
from app.schemas.review import (
    ReviewCreateEnvelope,
    ReviewDetailResponse,
    ReviewListResponse,
    ReviewListItem,
    ReviewDeleteRequest,
    ReviewDeleteResponse,
    MetricsRequest,
    MetricsResponse,
    MetricsPoint,
    LLMRequest,
    LLMResponse,
    ReviewCheckRequest,
    ReviewCheckResponse,
    ReviewResultPatch,
    ReviewCategoryResult,
    ReviewRequest,
    ReviewRequestResponse,
    ReviewRequestResponseBody,
    ReviewListRequest,
    ReviewListResponse,
    ReviewListResponseBody,
    ReviewListItem,
    ReviewDetailResponse,
    ReviewDetailResponseBody,
    ReviewDetailCategory,
    ReviewResultMeta,
)
from app.models.review import Review
from app.models.action_log import ActionLog
from app.services.llm_client import review_code
from app.routers.auth import get_current_user_id
from app.routers.ws import ws_manager  # ws_manager import
from app.schemas.review import (
    ReviewCheckRequest,
    ReviewCheckResponse,
    ReviewCheckResponseBody,
)
from app.schemas.common import Meta
from app.schemas.review import ReviewResultRequest
from fastapi import Path
router = APIRouter(prefix="/v1/reviews", tags=["review"])


# ======================================================================
# 공통 유틸
# ======================================================================

def normalize_scores(llm_scores: dict) -> dict:
    global_score = llm_scores.get("global", 0)
    model_score = llm_scores.get("model", 0)
    efficiency_index = round((model_score / global_score), 2) if global_score else 0.0
    return {
        "global_score": global_score,
        "model_score": model_score,
        "efficiency_index": efficiency_index,
    }


def make_request_hash(user_id: int, code: str, language: str) -> str:
    raw = f"{user_id}:{language}:{code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_code_fingerprint(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# ======================================================================
# 1) 리뷰 생성 요청  (POST /v1/reviews/request)
# ======================================================================

@router.post("/request", response_model=ReviewRequestResponse)
async def request_review(
    payload: ReviewRequest,
    session: AsyncSession = Depends(get_session),
):
    body = payload.body

    # 코드 fingerprint
    code_fingerprint = sha256(body.snippet.code.encode("utf-8")).hexdigest()

    # Review 레코드 생성
    review = Review(
        user_id=body.user_id,
        language=body.snippet.language,
        file_path=body.snippet.file_path,
        code=body.snippet.code,
        code_fingerprint=code_fingerprint,
        trigger=body.trigger,
        status="pending",
        global_score=None,
        model_score=None,
        efficiency_index=None,
    )
    session.add(review)
    await session.flush()  # review.id 생성

    # TODO: 여기서 LLM worker 큐에 job 넣기 등

    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    resp_meta = Meta(
        id=review.id,
        version="v1",
        actor="server",
        identity=payload.meta.identity,
        model=payload.meta.model,
        analysis=payload.meta.analysis,
        progress={"status": "pending", "next_step": 1},
        result=None,
        audit={
            "created_at": now,
            "updated_at": now,
        },
    )

    resp_body = ReviewRequestResponseBody(
        review_id=review.id,
        status=review.status,
    )

    await session.commit()

    return ReviewRequestResponse(meta=resp_meta, body=resp_body)

# ======================================================================
# 2) 리뷰 신규성 확인  (POST /v1/reviews/check)
# ======================================================================

@router.post("/check", response_model=ReviewCheckResponse)
async def check_review(
    req: ReviewCheckRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    문서의 '리뷰 신규성 확인'에 해당.
    request_hash 기준으로 동일 요청 여부 확인.
    """
    request_hash = make_request_hash(req.user_id, req.code, req.language)

    stmt = (
        select(Review)
        .where(Review.request_hash == request_hash)
        .order_by(Review.created_at.desc())
        .limit(1)
    )
    rec = (await session.execute(stmt)).scalar_one_or_none()

    if rec is None:
        return ReviewCheckResponse(
            is_new=True,
            reason="no_recent_review",
            last_review_id=None,
        )

    # 같은 해시 == 같은 코드/언어 조합
    return ReviewCheckResponse(
        is_new=False,
        reason="same_code",
        last_review_id=rec.id,
    )


# ======================================================================
# 3) 분석 결과 패치 저장  (PATCH /v1/reviews/{review_id}/result)
#   - 문서의 "분석 정보 저장"에 해당
# ======================================================================

@router.patch("/{review_id}/result")
async def save_review_result(
    review_id: int = Path(...),
    payload: ReviewResultRequest = ...,
    session: AsyncSession = Depends(get_session),
):
    record = payload.record

    stmt = select(Review).where(Review.id == review_id)
    result = await session.execute(stmt)
    review: Review | None = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Review 테이블 업데이트 (필요하면 review_result 별도 테이블 둬도 됨)
    review.global_score = record.scores.global_score
    review.model_score = record.scores.model_score
    review.efficiency_index = record.scores.efficiency_index
    review.summary = record.summary
    review.status = record.status

    await session.commit()

    return {"status": "ok"}
# ======================================================================
# 4) 리뷰 목록 조회  (GET /v1/reviews)
# ======================================================================

@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    payload: ReviewListRequest,
    session: AsyncSession = Depends(get_session),
):
    body = payload.request
    page = max(body.page, 1)
    page_size = 20
    offset = (page - 1) * page_size

    conditions = [Review.user_id == body.user_id]
    if body.filters.language:
        conditions.append(Review.language == body.filters.language)

    stmt = (
        select(Review)
        .where(and_(*conditions))
        .order_by(desc(Review.created_at))
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    reviews: list[Review] = result.scalars().all()

    items = [
        ReviewListItem(
            review_id=r.id,
            global_score=r.global_score,
            model_score=r.model_score,
            efficiency_index=r.efficiency_index,
            summary=r.summary,
            trigger=r.trigger,
            status=r.status,
            created_at=r.created_at.isoformat().replace("+00:00", "Z"),
        )
        for r in reviews
    ]

    meta = ReviewResultMeta(
        version=payload.meta.version,
        ts=payload.meta.ts,
        correlation_id=payload.meta.correlation_id,
        actor="server",
    )

    return ReviewListResponse(
        meta=meta,
        response=ReviewListResponseBody(items=items),
    )


@router.get("/{review_id}", response_model=ReviewDetailResponse)
async def get_review_detail(
    review_id: int,
    ts: str,
    correlation_id: str,
    session: AsyncSession = Depends(get_session),
):
    # NOTE: 여기선 meta를 query param으로 받게 예시. 필요하면 Request body로 바꿔도 됨.
    stmt = select(Review).where(Review.id == review_id)
    result = await session.execute(stmt)
    review: Review | None = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # TODO: categories 는 별도 테이블에서 가져오거나 JSON 컬럼에서 파싱
    categories: list[ReviewDetailCategory] = []

    meta = ReviewResultMeta(
        version="v1",
        ts=ts,
        correlation_id=correlation_id,
        actor="server",
    )

    body = ReviewDetailResponseBody(
        review_id=review.id,
        global_score=review.global_score,
        model_score=review.model_score,
        efficiency_index=review.efficiency_index,
        summary=review.summary,
        trigger=review.trigger,
        status=review.status,
        created_at=review.created_at.isoformat().replace("+00:00", "Z"),
        categories=categories,
    )

    return ReviewDetailResponse(meta=meta, response=body)
# ======================================================================
# 6) 삭제 / 메트릭스 (문서 9, 10, 11쪽 대응)
# ======================================================================

@router.post("/delete", response_model=ReviewDeleteResponse)
async def delete_reviews(
    body: ReviewDeleteRequest,
    session: AsyncSession = Depends(get_session),
):
    req = body.request

    if req.scope == "single" and req.review_id is None:
        raise HTTPException(status_code=400, detail="review_id required for 'single'")

    deleted = 0

    if req.scope == "single":
        stmt = select(Review).where(
            Review.user_id == req.user_id,
            Review.id == req.review_id,
        )
        res = await session.execute(stmt)
        row = res.scalars().first()
        if row:
            await session.delete(row)
            deleted = 1
    else:  # "all"
        stmt = select(Review).where(Review.user_id == req.user_id)
        res = await session.execute(stmt)
        rows = res.scalars().all()
        deleted = len(rows)
        for r in rows:
            await session.delete(r)

    await session.commit()

    return ReviewDeleteResponse(
        meta=body.meta,
        response={"deleted": deleted},
    )


@router.post("/metrics", response_model=MetricsResponse)
async def review_metrics(
    body: MetricsRequest,
    session: AsyncSession = Depends(get_session),
):
    req = body.request

    stmt = (
        select(
            func.date(Review.created_at).label("date"),
            func.avg(Review.scores["global_score"]).label("global_score_avg"),
            func.avg(Review.scores["model_score"]).label("model_score_avg"),
        )
        .where(Review.user_id == req.user_id)
        .group_by(func.date(Review.created_at))
        .order_by(func.date(Review.created_at))
    )

    res = await session.execute(stmt)
    rows = res.all()

    series = [
        MetricsPoint(
            date=str(r.date),
            global_score_avg=float(r.global_score_avg or 0),
            model_score_avg=float(r.model_score_avg or 0),
        )
        for r in rows
    ]

    return MetricsResponse(
        meta=body.meta,
        response={"series": series},
    )
@router.post("/check", response_model=ReviewCheckResponse)
async def check_review_newness(
    payload: ReviewCheckRequest,
    session: AsyncSession = Depends(get_session),
):
    body = payload.body

    # code fingerprint 예시: sha256(code)
    code_fingerprint = sha256(body.code.encode("utf-8")).hexdigest()

    # 최근 리뷰 1건 찾아보기 (user + fingerprint 기준)
    stmt = (
        select(Review)
        .where(
            Review.user_id == body.user_id,
            Review.code_fingerprint == code_fingerprint,
        )
        .order_by(desc(Review.created_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    last_review: Review | None = result.scalar_one_or_none()

    if last_review is None:
        is_new = True
        reason = "no_recent_review"
        last_review_id = None
    else:
        # 여기서 "최근" 기준(예: 1시간/하루/etc) 정해서 reason 바꿔도 됨
        is_new = False
        reason = "recent_review"
        last_review_id = last_review.id

    now = datetime(2025, 11, 12, 8, 0, 1, tzinfo=timezone.utc)
    resp_meta = Meta(
        id=None,
        version="v1",
        actor="server",
        identity=None,
        model=None,
        analysis=None,
        progress={"status": "done", "next_step": None},
        result=None,
        audit={
            "created_at": now,
            "updated_at": now,
        },
    )

    resp_body = ReviewCheckResponseBody(
        is_new=is_new,
        reason=reason,
        last_review_id=last_review_id,
    )

    return ReviewCheckResponse(meta=resp_meta, body=resp_body)

