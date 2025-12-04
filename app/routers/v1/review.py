from uuid import uuid4
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_, desc
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
    ModelStatsResponse,
    ModelStatsItem,
    UserStatsResponse,
    UserStatsItem,
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
    """UTC → KST 변환 후 ISO 문자열 반환"""
    if not audit_dt:
        audit_dt = datetime.now(timezone.utc)
    kst = audit_dt.astimezone(timezone(timedelta(hours=9)))
    return kst.isoformat().replace("+09:00", "")

async def emit_review_event(event_type: str, payload: dict) -> None:
    await ws_manager.broadcast({"type": event_type, "payload": payload})

def parse_date_utc(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


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

    if not body.snippet or not body.snippet.code:
        raise HTTPException(status_code=400, detail="code snippet is empty")

    github_id = getattr(meta, "github_id", None)
    if not github_id:
        raise HTTPException(status_code=400, detail="meta.github_id is required")

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
        github_id=str(github_id),
        model=model_id,
        trigger=trigger,
        language=language,
        llm_result=llm_res,
        code_fingerprint=code_fingerprint,
    )

    meta_row = await session.get(ReviewMeta, review.meta_id)
    if meta_row and not meta_row.github_id:
        meta_row.github_id = str(github_id)
        session.add(meta_row)

    await emit_review_event(
        "review_saved",
        {
            "correlation_id": correlation_id,
            "github_id": str(github_id),
            "review_id": int(review.id),
            "user_id": user_id,
        },
    )

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



@router.get("/stats/by-model", response_model=ModelStatsResponse)
async def get_stats_by_model(
    session: AsyncSession = Depends(get_session),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
) -> ModelStatsResponse:
    from_dt = parse_date_utc(from_)
    to_dt = parse_date_utc(to)

    if to_dt:
        to_dt = to_dt + timedelta(days=1)

    conditions = []
    if from_dt:
        conditions.append(ReviewMeta.audit >= from_dt)
    if to_dt:
        conditions.append(ReviewMeta.audit < to_dt)

    stmt = (
        select(
            ReviewMeta.model.label("model"),
            func.count(func.distinct(Review.id)).label("review_count"),
            func.avg(Review.quality_score).label("avg_total"),
            func.avg(
                case(
                    (ReviewCategoryResult.category == "bug", ReviewCategoryResult.score),
                    else_=None,
                )
            ).label("avg_bug"),
            func.avg(
                case(
                    (
                        ReviewCategoryResult.category == "maintainability",
                        ReviewCategoryResult.score,
                    ),
                    else_=None,
                )
            ).label("avg_maintainability"),
            func.avg(
                case(
                    (ReviewCategoryResult.category == "style", ReviewCategoryResult.score),
                    else_=None,
                )
            ).label("avg_style"),
            func.avg(
                case(
                    (ReviewCategoryResult.category == "security", ReviewCategoryResult.score),
                    else_=None,
                )
            ).label("avg_security"),
        )
        .select_from(ReviewMeta)
        .outerjoin(Review, Review.meta_id == ReviewMeta.id)
        .outerjoin(ReviewCategoryResult, ReviewCategoryResult.review_id == Review.id)
        .group_by(ReviewMeta.model)
        .order_by(ReviewMeta.model)
    )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await session.execute(stmt)
    rows = result.all()

    items: list[ModelStatsItem] = []
    for row in rows:
        items.append(
            ModelStatsItem(
                model=row.model,
                review_count=int(row.review_count or 0),
                avg_total=float(row.avg_total) if row.avg_total is not None else None,
                avg_bug=float(row.avg_bug) if row.avg_bug is not None else None,
                avg_maintainability=float(row.avg_maintainability)
                if row.avg_maintainability is not None
                else None,
                avg_style=float(row.avg_style) if row.avg_style is not None else None,
                avg_security=float(row.avg_security) if row.avg_security is not None else None,
            )
        )

    return ModelStatsResponse(data=items)

@router.get("/stats/by-user", response_model=UserStatsResponse)
async def get_stats_by_user(
    session: AsyncSession = Depends(get_session),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
    model: str | None = Query(None),
    limit: int | None = Query(None, ge=1),
) -> UserStatsResponse:
    from_dt = parse_date_utc(from_)
    to_dt = parse_date_utc(to)
    if to_dt:
        to_dt = to_dt + timedelta(days=1)

    conditions = []
    if from_dt:
        conditions.append(ReviewMeta.audit >= from_dt)
    if to_dt:
        conditions.append(ReviewMeta.audit < to_dt)
    if model:
        conditions.append(ReviewMeta.model == model)

    stmt = (
        select(
            User.id.label("user_id"),
            User.github_id.label("github_id"),
            func.count(func.distinct(Review.id)).label("review_count"),
            func.avg(Review.quality_score).label("avg_total"),
            func.avg(
                case(
                    (ReviewCategoryResult.category == "bug", ReviewCategoryResult.score),
                    else_=None,
                )
            ).label("avg_bug"),
            func.avg(
                case(
                    (
                        ReviewCategoryResult.category == "maintainability",
                        ReviewCategoryResult.score,
                    ),
                    else_=None,
                )
            ).label("avg_maintainability"),
            func.avg(
                case(
                    (ReviewCategoryResult.category == "style", ReviewCategoryResult.score),
                    else_=None,
                )
            ).label("avg_style"),
            func.avg(
                case(
                    (ReviewCategoryResult.category == "security", ReviewCategoryResult.score),
                    else_=None,
                )
            ).label("avg_security"),
        )
        .join(ReviewMeta, Review.meta_id == ReviewMeta.id)
        .join(User, User.github_id == ReviewMeta.github_id) 
        .join(ReviewCategoryResult, ReviewCategoryResult.review_id == Review.id)
        .group_by(User.id, User.github_id)
        .order_by(desc(func.avg(Review.quality_score)))  
    )

    if conditions:
        stmt = stmt.where(and_(*conditions))
    if limit:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    items: list[UserStatsItem] = []
    for row in rows:
        items.append(
            UserStatsItem(
                user_id=int(row.user_id),
                github_id=row.github_id,
                review_count=int(row.review_count or 0),
                avg_total=float(row.avg_total) if row.avg_total is not None else None,
                avg_bug=float(row.avg_bug) if row.avg_bug is not None else None,
                avg_maintainability=float(row.avg_maintainability)
                if row.avg_maintainability is not None
                else None,
                avg_style=float(row.avg_style) if row.avg_style is not None else None,
                avg_security=float(row.avg_security) if row.avg_security is not None else None,
            )
        )

    return UserStatsResponse(data=items)
