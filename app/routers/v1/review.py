# app/routers/v1/review.py
from uuid import uuid4
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Path
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
    ReviewListResponseBody,
    ReviewDetailResponseBody,
    ReviewDetailCategory,
    ReviewResultMeta,
    ReviewCheckResponseBody,
    ReviewResultRequest,
)
from app.models.review import Review
from app.models.action_log import ActionLog
from app.services.llm_client import review_code
from app.routers.auth import get_current_user_id
from app.routers.ws_debug import ws_manager  # WebSocket manager

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
    return sha256(raw.encode("utf-8")).hexdigest()


def make_code_fingerprint(code: str) -> str:
    return sha256(code.encode("utf-8")).hexdigest()


async def ws_trace(event: str, step: int | None = None, payload: dict | None = None):
    if not ws_manager:
        return

    message = {
        "event": event,
        "step": step,
        "payload": payload or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await ws_manager.broadcast(message)


# ======================================================================
# 1) 리뷰 생성 요청  (POST /v1/reviews/request)  - 다이어그램 Step 2
# ======================================================================

@router.post("/request", response_model=ReviewRequestResponse)
async def request_review(
    payload: ReviewRequest,
    session: AsyncSession = Depends(get_session),
):
    body = payload.body

    # -----------------------------
    # 0. 공통 값 파싱
    # -----------------------------
    code = body.snippet.code
    language = body.snippet.language
    file_path = body.snippet.file_path

    # fingerprint / request_hash 계산
    code_fingerprint = make_code_fingerprint(code)
    request_hash = make_request_hash(body.user_id, code, language)

    # model 정보는 body가 아니라 meta.model.name 에서 꺼내자
    model_name: str | None = None
    if payload.meta and getattr(payload.meta, "model", None):
        m = payload.meta.model
        if isinstance(m, dict):
            model_name = m.get("name")
        else:
            model_name = getattr(m, "name", None)

    # 분석 관점(aspects)도 meta.analysis에서 꺼냄
    aspects: list[str] = []
    if payload.meta and getattr(payload.meta, "analysis", None):
        a = payload.meta.analysis
        if isinstance(a, dict):
            aspects = a.get("aspects") or []
        else:
            aspects = getattr(a, "aspects", []) or []

    # WS 디버그: 리뷰 생성 요청 들어옴 (Step 2)
    await ws_trace(
        event="review_request_received",
        step=2,
        payload={
            "user_id": body.user_id,
            "language": language,
            "model": model_name,
            "has_code": bool(code),
        },
    )

    # -----------------------------
    # 1. Review 레코드 먼저 생성 (status: processing)
    # -----------------------------
    review = Review(
        user_id=body.user_id,
        language=language,
        file_path=file_path,
        code=code,
        code_fingerprint=code_fingerprint,
        # request_hash=request_hash,
        trigger=body.trigger,
        status="processing",
    )
    session.add(review)
    await session.flush()  # review.id 확보

    # -----------------------------
    # 2. LLM 요청 만들고 호출
    #    (여기서 LLM 죽으면 llm_client에서 더미로 폴백)
    # -----------------------------
    llm_req = LLMRequest(
        code=code,
        language=language,
        criteria=aspects,
        model=model_name,
    )

    llm_resp = await review_code(llm_req)

    # -----------------------------
    # 3. LLM(또는 더미) 결과를 Review에 저장
    # -----------------------------
    g = llm_resp.scores.get("global")
    m = llm_resp.scores.get("model")
    eff = (m / g) if g else None

    # 숫자 컬럼 채우기 (기본)
    if hasattr(review, "global_score"):
        review.global_score = g
    if hasattr(review, "model_score"):
        review.model_score = m
    if hasattr(review, "efficiency_index"):
        review.efficiency_index = eff

    # scores JSON 컬럼이 있으면 같이 채우기
    if hasattr(review, "scores"):
        review.scores = {
            "global_score": g,
            "model_score": m,
            "efficiency_index": eff,
        }

    review.summary = llm_resp.summary

    # categories JSON 컬럼이 있으면 채우기
    if hasattr(review, "categories"):
        try:
            review.categories = [c.dict() for c in llm_resp.categories]
        except AttributeError:
            review.categories = [
                {
                    "name": getattr(c, "name", ""),
                    "score": getattr(c, "score", 0),
                    "comment": getattr(c, "comment", ""),
                }
                for c in llm_resp.categories
            ]

    review.status = "done"

    await session.commit()

    # -----------------------------
    # 4. 응답 meta/body 만들기
    # -----------------------------
    resp_meta = payload.meta
    if resp_meta:
        if isinstance(resp_meta, Meta):
            resp_meta.progress = {"status": "done", "next_step": None}
        else:
            resp_meta["progress"] = {"status": "done", "next_step": None}

    resp_body = ReviewRequestResponseBody(
        review_id=review.id,
        status=review.status,
    )

    # VSCode/WEB 응답 직전 WebSocket (Step 6 느낌)
    await ws_trace(
        event="analysis_response_returned",
        step=6,
        payload={
            "review_id": review.id,
            "user_id": review.user_id,
            "status": review.status,
            "global_score": g,
            "model_score": m,
        },
    )

    return ReviewRequestResponse(meta=resp_meta, body=resp_body)


# ======================================================================
# 2) 리뷰 신규성 확인  (POST /v1/reviews/check)  - 다이어그램 Step 1
# ======================================================================

@router.post("/check", response_model=ReviewCheckResponse)
async def check_review(
    payload: ReviewCheckRequest,
    session: AsyncSession = Depends(get_session),
):
    body = payload.body

    # code fingerprint: sha256(code)
    code_fingerprint = make_code_fingerprint(body.code)

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

    # WS 디버그: 신규성 체크 (Step 1)
    await ws_trace(
        event="review_new_check",
        step=1,
        payload={
            "user_id": body.user_id,
            "language": body.language,
            "is_new": is_new,
            "reason": reason,
            "last_review_id": last_review_id,
        },
    )

    return ReviewCheckResponse(meta=resp_meta, body=resp_body)


# ======================================================================
# 3) 분석 결과 패치 저장  (PATCH /v1/reviews/{review_id}/result)
#    - 문서의 "분석 정보 저장" / 다이어그램 Step 5
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

    # Review 테이블 업데이트
    review.global_score = record.scores.global_score
    review.model_score = record.scores.model_score
    review.efficiency_index = record.scores.efficiency_index
    review.summary = record.summary
    review.status = record.status

    await session.commit()

    # WS 디버그: 분석 결과 저장 (Step 5)
    await ws_trace(
        event="analysis_saved_to_db",
        step=5,
        payload={
            "review_id": review_id,
            "status": review.status,
        },
    )

    return {"status": "ok"}


# ======================================================================
# 4) 리뷰 목록 조회  (GET /v1/reviews)  - 다이어그램 Step 6 (분석 정보 제공)
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

    # WS 디버그: 목록 조회 (Step 6)
    await ws_trace(
        event="review_list_provided",
        step=6,
        payload={
            "user_id": body.user_id,
            "page": page,
            "item_count": len(items),
        },
    )

    return ReviewListResponse(
        meta=meta,
        response=ReviewListResponseBody(items=items),
    )


# ======================================================================
# 5) 리뷰 상세 조회  (GET /v1/reviews/{review_id})  - 다이어그램 Step 6
# ======================================================================

@router.get("/{review_id}", response_model=ReviewDetailResponse)
async def get_review_detail(
    review_id: int,
    ts: str,
    correlation_id: str,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Review).where(Review.id == review_id)
    result = await session.execute(stmt)
    review: Review | None = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # categories JSON 컬럼 → 응답 모델로 매핑
    categories: list[ReviewDetailCategory] = []
    try:
        raw_cats = review.categories or []
        for c in raw_cats:
            categories.append(
                ReviewDetailCategory(
                    name=c.get("name", ""),
                    score=c.get("score", 0),
                    comment=c.get("comment", ""),
                )
            )
    except Exception:
        categories = []

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

    # WS 디버그: 상세 조회 (Step 6)
    await ws_trace(
        event="review_detail_provided",
        step=6,
        payload={
            "review_id": review_id,
            "status": review.status,
        },
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

    # WS 디버그: 리뷰 삭제 이벤트
    await ws_trace(
        event="review_deleted",
        step=None,
        payload={
            "user_id": req.user_id,
            "deleted": deleted,
            "scope": req.scope,
            "review_id": req.review_id,
        },
    )

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

    await ws_trace(
        event="review_metrics_queried",
        step=None,
        payload={
            "user_id": req.user_id,
            "points": len(series),
        },
    )

    return MetricsResponse(
        meta=body.meta,
        response={"series": series},
    )
