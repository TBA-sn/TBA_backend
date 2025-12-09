# app/routers/ui_sample_import.py

from typing import Any
import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_session
from app.models.review import Review, ReviewMeta, ReviewCategoryResult

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/sample_import", response_class=HTMLResponse)
async def sample_import_form(request: Request):
    return templates.TemplateResponse(
        "ui/sample_import.html",
        {
            "request": request,
            "inserted": None,
            "error": None,
        },
    )


@router.post("/sample_import", response_class=HTMLResponse)
async def sample_import_post(
    request: Request,
    github_id: str = Form(...),
    json_file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    inserted = 0
    error_msg: str | None = None

    try:
        raw = await json_file.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError:
            data = json.loads(raw.decode("cp949"))

        # 배열 / 단일 객체 모두 처리
        if isinstance(data, list):
            items: list[dict[str, Any]] = data
        elif isinstance(data, dict):
            items = [data]
        else:
            raise ValueError("JSON은 배열 또는 객체 형태여야 합니다.")

        for payload in items:
            meta_json = payload.get("meta") or {}
            body_json = payload.get("body") or {}

            # 1) review_meta 먼저 생성
            # github_id 는 UI에서 받은 값으로 강제 세팅
            audit_raw = meta_json.get("audit")
            audit_dt = None
            if audit_raw:
                try:
                    # "2025-12-03T15:48:11" 형태라고 가정
                    audit_dt = datetime.fromisoformat(audit_raw)
                except Exception:
                    audit_dt = None  # 포맷 이상하면 그냥 None

            review_meta = ReviewMeta(
                github_id=github_id,
                version=meta_json.get("version") or "v1",
                language=meta_json.get("language") or "plaintext",
                trigger=meta_json.get("trigger") or "manual",
                code_fingerprint=meta_json.get("code_fingerprint") or "",
                model=meta_json.get("model") or "",
                audit=audit_dt,
            )
            session.add(review_meta)
            await session.flush()  # review_meta.id 확보

            # 2) review 생성 (review.meta_id 로 연결)
            review = Review(
                quality_score=body_json.get("quality_score"),
                summary=body_json.get("summary"),
                meta_id=review_meta.id,
            )
            session.add(review)
            await session.flush()  # review.id 확보

            # 3) review_category_result 여러 줄 생성
            scores = body_json.get("scores_by_category") or {}
            comments = body_json.get("comments") or {}

            for category, score in scores.items():
                cr = ReviewCategoryResult(
                    review_id=review.id,
                    category=category,
                    score=score,
                    comment=comments.get(category),
                )
                session.add(cr)

        await session.commit()
        inserted = len(items)

    except Exception as e:
        await session.rollback()
        error_msg = str(e)

    return templates.TemplateResponse(
        "ui/sample_import.html",
        {
            "request": request,
            "inserted": inserted if not error_msg else None,
            "error": error_msg,
        },
    )
