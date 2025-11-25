# app/routers/v1/review.py

from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.utils.database import get_session
from app.models.review import Review
from app.models.action_log import ActionLog
from app.schemas.common import Meta
from app.schemas.review import (
    ReviewRequest,
    ReviewRequestResponse,
    ReviewRequestResponseBody,
    LLMRequest,
    LLMQualityResponse,
)
from app.services.llm_client import review_code
from app.services.review_service import save_review_result
from app.routers.ws_debug import ws_manager   # 🔥 WebSocket 매니저

router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


# ─────────────────────────────────────────
#  공통: WebSocket 이벤트 헬퍼
# ─────────────────────────────────────────
async def emit_review_event(event_type: str, payload: dict) -> None:
    """
    리뷰 파이프라인 단계별로 WebSocket 이벤트를 쏘는 공통 함수.
    """
    await ws_manager.broadcast({
        "type": event_type,
        "payload": payload,
    })


@router.post("/request", response_model=ReviewRequestResponse)
async def create_review_request(
    envelope: ReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewRequestResponse:
    meta = envelope.meta
    body = envelope.body

    if not body.snippet or not body.snippet.code:
        raise HTTPException(status_code=400, detail="code snippet is empty")

    user_id = body.user_id
    correlation_id = getattr(meta, "correlation_id", None)

    raw_model = getattr(meta, "model", None)
    model_id = "unknown"
    if raw_model:
        if isinstance(raw_model, dict):
            model_id = raw_model.get("name") or "unknown"
        else:
            model_id = getattr(raw_model, "name", None) or "unknown"

    language = body.snippet.language or "unknown"
    trigger = body.trigger

    raw_analysis = getattr(meta, "analysis", None)
    if raw_analysis:
        if isinstance(raw_analysis, dict):
            aspects = raw_analysis.get("aspects") or []
        else:
            aspects = getattr(raw_analysis, "aspects", []) or []
    else:
        aspects = []

    # 1️⃣ 요청 들어옴
    await emit_review_event(
        "review_request_received",
        {
            "correlation_id": correlation_id,
            "user_id": user_id,
            "language": language,
            "model": model_id,
            "trigger": trigger,
            "aspects": aspects,
        },
    )

    llm_req = LLMRequest(
        code=body.snippet.code,
        language=language,
        model=model_id,
        criteria=aspects,
    )

    # 2️⃣ LLM 요청 보냄
    await emit_review_event(
        "llm_request_sent",
        {
            "correlation_id": correlation_id,
            "user_id": user_id,
            "model": model_id,
            "language": language,
        },
    )

    llm_res: LLMQualityResponse = await review_code(llm_req)

    # 3️⃣ LLM 응답 받음
    await emit_review_event(
        "llm_response_received",
        {
            "correlation_id": correlation_id,
            "user_id": user_id,
            "model": model_id,
            "language": language,
            "quality_score": int(llm_res.quality_score),
        },
    )

    review: Review = await save_review_result(
        session,
        user_id=user_id,
        model=model_id,
        trigger=trigger,
        language=language,
        llm_result=llm_res,
    )

    # 4️⃣ DB 저장 직후
    await emit_review_event(
        "review_saved",
        {
            "correlation_id": correlation_id,
            "review_id": int(review.id),
            "user_id": int(review.user_id),
        },
    )

    log = ActionLog(
        user_id=user_id,
        event_name="REVIEW_REQUEST",
        properties={
            "correlation_id": correlation_id,
            "language": language,
            "model": model_id,
            "review_id": int(review.id),
            "trigger": trigger,
        },
    )
    session.add(log)
    await session.commit()

    # 5️⃣ 전체 완료
    await emit_review_event(
        "review_completed",
        {
            "correlation_id": correlation_id,
            "review_id": int(review.id),
            "user_id": int(review.user_id),
            "language": review.language,
            "model": review.model,
            "trigger": review.trigger,
            "quality_score": int(review.quality_score),
            "summary": review.summary,
            "scores_by_category": {
                "bug": review.score_bug,
                "maintainability": review.score_maintainability,
                "style": review.score_style,
                "security": review.score_security,
            },
        },
    )

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")

    resp_meta = Meta(
        id=None,
        version=getattr(meta, "version", None) or "v1",
        actor="server",
        identity=getattr(meta, "identity", None),
        model=getattr(meta, "model", None),
        analysis=getattr(meta, "analysis", None),
        progress={"status": review.status, "next_step": None},
        result={"result_ref": str(review.id), "error_message": None},
        audit={
            "created_at": now_iso,
            "updated_at": now_iso,
        },
    )

    resp_body = ReviewRequestResponseBody(
        review_id=review.id,
        status=review.status,
    )

    return ReviewRequestResponse(meta=resp_meta, body=resp_body)


@router.get("/{review_id}", response_model=dict)
async def get_review_raw(
    review_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Review).where(Review.id == review_id)
    rec = (await session.execute(stmt)).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="review not found")

    return {
        "id": rec.id,
        "user_id": rec.user_id,
        "model": rec.model,
        "trigger": rec.trigger,
        "language": rec.language,
        "quality_score": rec.quality_score,
        "summary": rec.summary,
        "score_bug": rec.score_bug,
        "score_maintainability": rec.score_maintainability,
        "score_style": rec.score_style,
        "score_security": rec.score_security,
        "comment_bug": rec.comment_bug,
        "comment_maintainability": rec.comment_maintainability,
        "comment_style": rec.comment_style,
        "comment_security": rec.comment_security,
        "status": rec.status,
        "created_at": rec.created_at,
        "updated_at": rec.updated_at,
    }
