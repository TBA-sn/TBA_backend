# app/routers/v1/__init__.py
from fastapi import APIRouter
from app.routers.v1.review import router as review_router
from app.routers.v1.analysis_llm import router as analysis_llm_router

router = APIRouter()
router.include_router(review_router)
router.include_router(analysis_llm_router)
