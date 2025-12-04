# app/routers/v1/fix.py
from typing import Dict

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.utils.database import get_session
from app.models.review import Review, ReviewMeta, ReviewCategoryResult
from app.schemas.review import FixRequest
from app.services.ai_client import CodeReviewerClient

router = APIRouter(prefix="/v1", tags=["fix"])

ai_client = CodeReviewerClient(
    vllm_url="http://18.205.229.159:8001/v1",
)

@router.post("/fix", response_model=str)
async def get_fix_review(
    payload: FixRequest,
    session: AsyncSession = Depends(get_session),
) -> str:
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

    meta_db: ReviewMeta | None = review.meta
    if not meta_db:
        raise HTTPException(status_code=500, detail="meta not found for review")

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

    fixed_code_str = await asyncio.to_thread(
        ai_client.get_fix,
        payload.code,      
        review.summary,    
        comments,        
    )

    return fixed_code_str
