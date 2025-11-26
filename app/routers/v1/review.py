# app/routers/v1/review.py

from uuid import uuid4
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.utils.database import get_session
from app.models.review import Review
from app.models.action_log import ActionLog
from app.models.user import User
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
from app.routers.ws_debug import ws_manager
from typing import List
from app.routers.auth import get_current_user_id_from_cookie


router = APIRouter(prefix="/v1/reviews", tags=["reviews"])

def normalize_code(code: str) -> str:
    if not code:
        return ""

    code = code.replace("\r\n", "\n").replace("\r", "\n")
    lines = code.split("\n")

    normalized_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            normalized_lines.append(stripped)

    return "\n".join(normalized_lines)


def make_code_fingerprint(code: str) -> str:
    normalized = normalize_code(code)
    return sha256(normalized.encode("utf-8")).hexdigest()


async def emit_review_event(event_type: str, payload: dict) -> None:
    await ws_manager.broadcast(
        {
            "type": event_type,
            "payload": payload,
        }
    )


@router.post("/request", response_model=ReviewRequestResponse)
async def create_review_request(
    envelope: ReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewRequestResponse:
    meta = envelope.meta
    body = envelope.body

    if not body.snippet or not body.snippet.code:
        raise HTTPException(status_code=400, detail="code snippet is empty")

    github_id = getattr(meta, "github_id", None)
    if not github_id:
        raise HTTPException(status_code=400, detail="meta.github_id is required")

    result = await session.execute(
        select(User).where(User.github_id == str(github_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="user not found for given github_id")

    user_id = int(user.id)

    correlation_id = getattr(meta, "correlation_id", None)

    raw_model = getattr(meta, "model", None)
    model_id = raw_model or "unknown"
    if raw_model:
        if isinstance(raw_model, dict):
            model_id = raw_model.get("name") or "unknown"
        else:
            model_id = getattr(raw_model, "name", None) or "unknown"

    language = getattr(meta, "language", None) or "unknown"
    trigger = getattr(meta, "trigger", None) or "unknown"

    raw_analysis = getattr(meta, "analysis", None)
    if raw_analysis:
        if isinstance(raw_analysis, dict):
            aspects = raw_analysis.get("aspects") or []
        else:
            aspects = getattr(raw_analysis, "aspects", []) or []
    else:
        aspects = []

    code_fingerprint = make_code_fingerprint(body.snippet.code)

    await emit_review_event(
        "review_request_received",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
            "user_id": user_id,
            "language": language,
            "model": model_id,
            "trigger": trigger,
            "aspects": aspects,
            "code_fingerprint": code_fingerprint,
        },
    )

    llm_req = LLMRequest(
        code=body.snippet.code,
        language=language,
        model=model_id,
        criteria=aspects,
    )

    await emit_review_event(
        "llm_request_sent",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
            "user_id": user_id,
            "model": model_id,
            "language": language,
        },
    )

    llm_res: LLMQualityResponse = await review_code(llm_req)

    await emit_review_event(
        "llm_response_received",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
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

    await emit_review_event(
        "review_saved",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
            "review_id": int(review.id),
            "user_id": int(review.user_id),
        },
    )

    log = ActionLog(
        user_id=user_id,
        event_name="REVIEW_REQUEST",
        properties={
            "github_id": str(github_id),
            "correlation_id": correlation_id,
            "language": language,
            "model": model_id,
            "review_id": int(review.id),
            "trigger": trigger,
        },
    )
    session.add(log)
    await session.commit()

    await emit_review_event(
        "review_completed",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
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
        github_id=str(github_id),
        review_id=int(review.id),
        version=getattr(meta, "version", None) or "v1",
        actor="server",
        language=language,
        trigger=trigger,
        code_fingerprint=code_fingerprint,
        model=model_id,
        result={"result_ref": str(review.id), "error_message": None},
        audit={
            "created_at": now_iso,
            "updated_at": now_iso,
        },
    )

    resp_body = ReviewRequestResponseBody(
        review_id=review.id,
    )

    return ReviewRequestResponse(meta=resp_meta, body=resp_body)


@router.get("/{review_id}", response_model=dict)
async def get_review_raw(
    review_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Review, User)
        .join(User, Review.user_id == User.id)
        .where(Review.id == review_id)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="review not found")

    rec, user = row

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")

    meta = Meta(
        github_id=user.github_id,
        review_id=rec.id,
        version="v1",
        actor="server",
        language=rec.language or "unknown",
        trigger=rec.trigger or "manual",
        code_fingerprint=None,
        model=rec.model,
        result={"result_ref": str(rec.id), "error_message": None},
        audit={
            "created_at": rec.created_at or now_iso,
            "updated_at": rec.updated_at or now_iso,
        },
    )

    body = {
        "quality_score": rec.quality_score,
        "summary": rec.summary,
        "scores_by_category": {
            "bug": rec.score_bug,
            "maintainability": rec.score_maintainability,
            "style": rec.score_style,
            "security": rec.score_security,
        },
        "comments": {
            "bug": rec.comment_bug,
            "maintainability": rec.comment_maintainability,
            "style": rec.comment_style,
            "security": rec.comment_security,
        },
    }

    return {
        "meta": meta.model_dump(),
        "body": body,
    }

@router.get("/me", response_model=dict)
async def get_my_reviews(
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id_from_cookie),
):
    # 1) 현재 로그인 유저 정보 가져오기
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # 2) 이 유저의 리뷰들 최신순 조회
    result = await session.execute(
        select(Review)
        .where(Review.user_id == user.id)
        .order_by(Review.created_at.desc())
    )
    reviews: List[Review] = result.scalars().all()

    now = datetime.now(timezone.utc)

    meta = Meta(
        github_id=user.github_id,
        review_id=None,
        version="v1",
        actor="server",
        language="python",
        trigger="manual",
        code_fingerprint=None,
        model=None,
        result={"result_ref": str(len(reviews)), "error_message": None},
        audit={
            "created_at": now,
            "updated_at": now,
        },
    )

    body = []
    for rec in reviews:
        body.append(
            {
                "review_id": rec.id,
                "user_id": rec.user_id,
                "model": rec.model,
                "trigger": rec.trigger,
                "language": rec.language,
                "quality_score": rec.quality_score,
                "summary": rec.summary,
                "scores_by_category": {
                    "bug": rec.score_bug,
                    "maintainability": rec.score_maintainability,
                    "style": rec.score_style,
                    "security": rec.score_security,
                },
                "comments": {
                    "bug": rec.comment_bug,
                    "maintainability": rec.comment_maintainability,
                    "style": rec.comment_style,
                    "security": rec.comment_security,
                },
                "created_at": rec.created_at,
                "updated_at": rec.updated_at,
            }
        )

    return {
        "meta": meta.model_dump(),
        "body": body,
    }
