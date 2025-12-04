from uuid import uuid4
from datetime import datetime, timezone
from hashlib import sha256
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.utils.database import get_session
from app.models.review import Review, ReviewMeta, ReviewCategoryResult
from app.models.action_log import ActionLog
from app.models.user import User
from app.schemas.common import Meta
from app.schemas.review import (
    ReviewRequest,
    ReviewRequestResponse,
    ReviewRequestResponseBody,
    LLMRequest,
    LLMQualityResponse,
    ScoresByCategory,
    ReviewResultBody,
    ReviewDetailResponse,
    ReviewListResponse,
    ReviewListItem,
    FixResponseBody, 
    FixRequest,
)
from app.services.llm_client import review_code
from app.services.review_service import save_review_result
from app.routers.ws_debug import ws_manager
from app.routers.auth import get_current_user_id_from_cookie


router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


# ─────────────────────────────────────────
#  공통 유틸
# ─────────────────────────────────────────

def normalize_code(code: str) -> str:
    if not code:
        return ""
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.strip() for line in code.split("\n") if line.strip())


def make_code_fingerprint(code: str) -> str:
    normalized = normalize_code(code)
    return sha256(normalized.encode("utf-8")).hexdigest()


def build_audit_value(audit_dt: datetime | None) -> str:
    """ReviewMeta.audit(datetime) → ISO8601 문자열(Z 포함)로 변환"""
    if not audit_dt:
        audit_dt = datetime.now(timezone.utc)
    return audit_dt.isoformat().replace("+00:00", "Z")


async def emit_review_event(event_type: str, payload: dict) -> None:
    await ws_manager.broadcast({"type": event_type, "payload": payload})


# ─────────────────────────────────────────
#  POST /v1/reviews/request
# ─────────────────────────────────────────

@router.post("/request", response_model=ReviewRequestResponse)
async def create_review_request(
    envelope: ReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewRequestResponse:
    meta = envelope.meta
    body = envelope.body

    # 1) 유효성 검사
    if not body.snippet or not body.snippet.code:
        raise HTTPException(status_code=400, detail="code snippet is empty")

    github_id = getattr(meta, "github_id", None)
    if not github_id:
        raise HTTPException(status_code=400, detail="meta.github_id is required")

    # 2) GitHub ID → User 매핑
    result = await session.execute(select(User).where(User.github_id == str(github_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="user not found for given github_id")

    user_id = int(user.id)
    correlation_id = getattr(meta, "correlation_id", None)

    raw_model = getattr(meta, "model", None)
    model_id = "unknown"
    if raw_model:
        if isinstance(raw_model, dict):
            model_id = raw_model.get("name") or "unknown"
        else:
            model_id = getattr(raw_model, "name", None) or str(raw_model)

    language = getattr(meta, "language", "unknown")
    trigger = getattr(meta, "trigger", "manual")

    raw_analysis = getattr(meta, "analysis", None)
    if isinstance(raw_analysis, dict):
        aspects = raw_analysis.get("aspects") or []
    else:
        aspects = getattr(raw_analysis, "aspects", []) if raw_analysis else []
    aspects = aspects or []

    code_fingerprint = make_code_fingerprint(body.snippet.code)

    # 이벤트: 요청 수신
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

    # 3) LLM 호출
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

    # 4) DB 저장 (ReviewMeta + Review + ReviewCategoryResult)
    review: Review = await save_review_result(
        session,
        github_id=str(github_id),
        model=model_id,
        trigger=trigger,
        language=language,
        llm_result=llm_res,
        code_fingerprint=code_fingerprint,
    )

    # 🔐 여기서 ReviewMeta.github_id가 비어 있으면 채워넣기
    meta_row = await session.get(ReviewMeta, review.meta_id)
    if meta_row and not meta_row.github_id:
        meta_row.github_id = str(github_id)
        session.add(meta_row)
        # commit은 아래에서 ActionLog까지 같이 할 거라 여기서는 flush만 되어도 충분

    await emit_review_event(
        "review_saved",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
            "review_id": int(review.id),
            "user_id": user_id,
        },
    )

    # 5) ActionLog
    session.add(
        ActionLog(
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
    )
    await session.commit()

    # 6) 완료 이벤트
    await emit_review_event(
        "review_completed",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
            "review_id": int(review.id),
            "user_id": user_id,
            "language": language,
            "model": model_id,
            "trigger": trigger,
            "quality_score": int(llm_res.quality_score),
            "summary": llm_res.review_summary,
            "scores_by_category": llm_res.scores_by_category.model_dump(),
        },
    )

    # 7) 응답 meta/body
    now = datetime.now(timezone.utc)
    audit_value = build_audit_value(now)

    resp_meta = Meta(
        github_id=str(github_id),
        review_id=int(review.id),
        version=getattr(meta, "version", "v1"),
        actor="server",
        language=language,
        trigger=trigger,
        code_fingerprint=code_fingerprint,
        model=model_id,
        result={"result_ref": str(review.id), "error_message": None},
        audit=audit_value,
    )

    resp_body = ReviewRequestResponseBody(review_id=review.id)
    return ReviewRequestResponse(meta=resp_meta, body=resp_body)


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Review)
        .join(ReviewMeta, Review.meta_id == ReviewMeta.id)
        .options(joinedload(Review.meta), joinedload(Review.categories))
        .order_by(ReviewMeta.audit.desc())
    )
    result = await session.execute(stmt)
    reviews: List[Review] = result.unique().scalars().all()

    now = datetime.now(timezone.utc)
    meta = Meta(
        github_id=None,
        review_id=None,
        version="v1",
        actor="server",
        language="python",
        trigger="manual",
        code_fingerprint=None,
        model=None,
        result={"result_ref": str(len(reviews)), "error_message": None},
        audit=build_audit_value(now),
    )

    body: List[ReviewListItem] = []

    for rec in reviews:
        rec_meta: ReviewMeta | None = rec.meta
        if not rec_meta:
            continue

        cat_map: Dict[str, ReviewCategoryResult] = {c.category: c for c in rec.categories}

        def score(name: str) -> int:
            c = cat_map.get(name)
            return int(c.score) if c and c.score is not None else 0

        def comment(name: str) -> str:
            c = cat_map.get(name)
            return c.comment or "" if c and c.comment is not None else ""

        body.append(
            ReviewListItem(
                review_id=int(rec.id),
                github_id=rec_meta.github_id,
                model=rec_meta.model or "unknown",
                trigger=rec_meta.trigger,
                language=rec_meta.language,
                quality_score=int(rec.quality_score),
                summary=rec.summary,
                scores_by_category=ScoresByCategory(
                    bug=score("bug"),
                    maintainability=score("maintainability"),
                    style=score("style"),
                    security=score("security"),
                ),
                comments={
                    "bug": comment("bug"),
                    "maintainability": comment("maintainability"),
                    "style": comment("style"),
                    "security": comment("security"),
                },
                audit=build_audit_value(rec_meta.audit),
            )
        )

    return ReviewListResponse(meta=meta, body=body)

# ─────────────────────────────────────────
#  GET /v1/reviews/me
# ─────────────────────────────────────────

@router.get("/me", response_model=dict)
async def get_my_reviews(
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id_from_cookie),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    stmt = (
        select(Review)
        .join(ReviewMeta, Review.meta_id == ReviewMeta.id)
        .options(joinedload(Review.meta), joinedload(Review.categories))
        .where(ReviewMeta.github_id == user.github_id)
        .order_by(ReviewMeta.audit.desc())

    )
    result = await session.execute(stmt)
    reviews: List[Review] = result.unique().scalars().all()

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
        audit=build_audit_value(now),
    )

    body: List[dict] = []
    for rec in reviews:
        rec_meta: ReviewMeta | None = rec.meta
        if not rec_meta:
            continue

        cat_map: Dict[str, ReviewCategoryResult] = {c.category: c for c in rec.categories}

        def score(name: str) -> int:
            c = cat_map.get(name)
            return int(c.score) if c and c.score is not None else 0

        def comment(name: str) -> str:
            c = cat_map.get(name)
            return c.comment or "" if c and c.comment is not None else ""

        body.append(
            {
                "review_id": rec.id,
                "user_id": user.id,
                "model": rec_meta.model or "unknown",
                "trigger": rec_meta.trigger,
                "language": rec_meta.language,
                "quality_score": rec.quality_score,
                "summary": rec.summary,
                "scores_by_category": {
                    "bug": score("bug"),
                    "maintainability": score("maintainability"),
                    "style": score("style"),
                    "security": score("security"),
                },
                "comments": {
                    "bug": comment("bug"),
                    "maintainability": comment("maintainability"),
                    "style": comment("style"),
                    "security": comment("security"),
                },
                "audit": build_audit_value(rec_meta.audit),
            }
        )

    return {"meta": meta.model_dump(), "body": body}

# ─────────────────────────────────────────
#  GET /v1/reviews/{review_id}
# ─────────────────────────────────────────

@router.get("/{review_id}", response_model=ReviewDetailResponse)
async def get_review_raw(
    review_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Review)
        .options(joinedload(Review.meta), joinedload(Review.categories))
        .where(Review.id == review_id)
    )
    result = await session.execute(stmt)
    review: Review | None = result.unique().scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="review not found")

    meta_db: ReviewMeta | None = review.meta
    if not meta_db:
        raise HTTPException(status_code=500, detail="meta not found for review")

    # 카테고리 점수/코멘트 매핑
    cat_map: Dict[str, ReviewCategoryResult] = {c.category: c for c in review.categories}

    def score(name: str) -> int:
        c = cat_map.get(name)
        return int(c.score) if c and c.score is not None else 0

    def comment(name: str) -> str:
        c = cat_map.get(name)
        return c.comment or "" if c and c.comment is not None else ""

    body = ReviewResultBody(
        quality_score=int(review.quality_score),
        summary=review.summary,
        scores_by_category=ScoresByCategory(
            bug=score("bug"),
            maintainability=score("maintainability"),
            style=score("style"),
            security=score("security"),
        ),
        comments={
            "bug": comment("bug"),
            "maintainability": comment("maintainability"),
            "style": comment("style"),
            "security": comment("security"),
        },
    )

    resp_meta = Meta(
        github_id=meta_db.github_id,
        review_id=review.id,
        version=meta_db.version,
        actor="server",
        language=meta_db.language,
        trigger=meta_db.trigger,
        code_fingerprint=meta_db.code_fingerprint,
        model=meta_db.model or "unknown",
        result={"result_ref": str(review.id), "error_message": None},
        audit=build_audit_value(meta_db.audit),
    )

    return ReviewDetailResponse(meta=resp_meta, body=body)


@router.post("/fix", response_model=FixResponseBody)
async def get_fix_review(
    payload: FixRequest,
    session: AsyncSession = Depends(get_session),
) -> FixResponseBody:
    review_id = payload.review_id

    stmt = (
        select(Review)
        .options(joinedload(Review.meta), joinedload(Review.categories))
        .where(Review.id == review_id)
    )
    result = await session.execute(stmt)
    review: Review | None = result.unique().scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="review not found")

    # meta는 응답에 안 쓰지만, 없는 건 말이 안 되니까 체크만
    meta_db: ReviewMeta | None = review.meta
    if not meta_db:
        raise HTTPException(status_code=500, detail="meta not found for review")

    # 카테고리별 코멘트 맵
    cat_map: Dict[str, ReviewCategoryResult] = {c.category: c for c in review.categories}

    def comment(name: str) -> str:
        c = cat_map.get(name)
        return c.comment or "" if c and c.comment is not None else ""

    comments = {
        "bug": comment("bug"),
        "maintainability": comment("maintainability"),
        "style": comment("style"),
        "security": comment("security"),
    }

    # code는 DB에서 안 꺼내고 VS Code가 보낸 payload.code 그대로 사용
    return FixResponseBody(
        code=payload.code,
        summary=review.summary,
        comments=comments,
    )