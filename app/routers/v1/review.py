from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.utils.database import get_session
from app.schemas.review import (
    ExtensionRequest, LLMRequest, LLMResponse,
    ReviewOut, LogCreate
)
from app.models.review import Review
from app.models.action_log import ActionLog
from app.services.llm_client import review_code
from app.routers.auth import get_current_user_id
from uuid import uuid4
router = APIRouter(prefix="/v1", tags=["review"])

@router.post("/reviews/request", response_model=ReviewOut, summary="리뷰 작성 요청")
async def create_review(
    req: ExtensionRequest,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id),
):
    llm_req = LLMRequest(code=req.code, model=req.model_id)
    llm_res: LLMResponse = await review_code(llm_req)

    review = Review(
        user_id=user_id,
        model_id=req.model_id,
        language=req.language,
        code=req.code,
        trigger=req.trigger,
        result=llm_res.model_dump(),
        summary=llm_res.summary,
    )
    session.add(review)
    await session.flush()

    log = ActionLog(
        log_id=f"lg-{uuid4().hex}", 
        user_id=user_id,
        case_id=str(review.id),
        action="REVIEW_REQUEST",
    )
    session.add(log)
    await session.commit()

    return ReviewOut(
        review_id=review.id,
        global_score=llm_res.scores["global"],
        model_score=llm_res.scores["model"],
        categories=[{"name": c.name, "score": c.score, "comment": getattr(c, "comment", None)} for c in llm_res.categories],
        summary=llm_res.summary,
    )

@router.get("/reviews/{review_id}", response_model=ReviewOut, summary="리뷰 단건 조회")
async def get_review(review_id: int, session: AsyncSession = Depends(get_session)):
    q = await session.execute(select(Review).where(Review.id == review_id))
    row = q.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "review not found")

    res = row.result if isinstance(row.result, dict) else {}
    scores = res.get("scores", {})
    cats = res.get("categories", [])
    categories = [{"name": (c.get("name") if isinstance(c, dict) else ""), "score": int((c.get("score") if isinstance(c, dict) else 0))} for c in cats]

    return ReviewOut(
        review_id=row.id,
        global_score=int(scores.get("global", 0)),
        model_score=int(scores.get("model", 0)),
        categories=categories,
        summary=res.get("summary", row.summary or ""),
    )

@router.get("/reviews", response_model=list[ReviewOut], summary="리뷰 목록 조회")
async def list_reviews(limit: int = 20, session: AsyncSession = Depends(get_session)):
    q = await session.execute(select(Review).order_by(Review.created_at.desc()).limit(limit))
    rows = q.scalars().all()
    out: list[ReviewOut] = []
    for r in rows:
        res = r.result if isinstance(r.result, dict) else {}
        scores = res.get("scores", {})
        cats = res.get("categories", [])
        categories = [{"name": (c.get("name") if isinstance(c, dict) else ""), "score": int((c.get("score") if isinstance(c, dict) else 0))} for c in cats]
        out.append(ReviewOut(
            review_id=r.id,
            global_score=int(scores.get("global", 0)),
            model_score=int(scores.get("model", 0)),
            categories=categories,
            summary=res.get("summary", r.summary or ""),
        ))
    return out
