# app/routers/ui.py
from uuid import uuid4
import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_session
from app.models.review import Review
from app.models.action_log import ActionLog
from app.routers.auth import get_current_user_id_from_cookie
import httpx

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/templates")

DEFAULT_CRITERIA: List[str] = [
    "유지보수성",
    "가독성",
    "확장성",
    "유연성",
    "간결성",
    "재사용성",
    "테스트 용이성",
]


async def _load_default_criteria(session: AsyncSession) -> List[str]:
    return DEFAULT_CRITERIA


def build_code_request_payload(
    *,
    user_id: int,
    model_id: str,
    language: str,
    trigger: str,
    code: str,
    aspects: List[str],
    file_path: str | None = None,
) -> dict:
    """
    POST /v1/reviews/request 에 맞는 Request Body 생성
    -> ReviewRequest 스키마: { "meta": {...}, "body": {...} }
    """
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    meta = {
        "version": "v1",
        "ts": now,
        "correlation_id": str(uuid4()),
        "actor": "web",
        "identity": None,
        "model": {
            "name": model_id,
        },
        "analysis": {
            "aspects": aspects,
            "total_steps": 6,
        },
        "progress": {"status": "pending", "next_step": 1},
        "result": None,
        "audit": None,
    }

    body = {
        "user_id": user_id,
        "snippet": {
            "code": code,
            "language": language,
            "file_path": file_path or "",
        },
        "trigger": trigger,
        "model": model_id,
    }

    # ✅ ReviewRequest(meta=..., body=...) 구조
    return {"meta": meta, "body": body}


# =====================================================================================
# 리뷰 폼
# =====================================================================================

@router.get("/review")
async def review_form(request: Request):
    return templates.TemplateResponse("ui/review_form.html", {"request": request})


@router.post("/review")
async def review_submit(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: int | None = Form(None),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
):
    # 쿠키에 user_id 있으면 그것 우선 사용
    try:
        uid = get_current_user_id_from_cookie(request)
    except Exception:
        uid = user_id

    if uid is None:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    criteria = await _load_default_criteria(session)

    payload = build_code_request_payload(
        user_id=int(uid),
        model_id=model_id,
        language=language,
        trigger=trigger,
        code=code,
        aspects=criteria,
    )

    url = "http://localhost:8000/v1/reviews/request"
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(url, json=payload)

    if res.status_code != 200:
        # 디버깅 필요하면 여기서 res.text 찍어봐도 됨
        return RedirectResponse(url="/ui/reviews", status_code=303)

    body = res.json()
    # ⬅️ ReviewRequestResponse(meta=..., body=...) 형태라 여기서 꺼내야 함
    resp_body = body.get("body") or {}
    review_id = resp_body.get("review_id")

    if not review_id:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    return RedirectResponse(url=f"/ui/review/{review_id}", status_code=303)


# =====================================================================================
# 리뷰 상세 / 리스트
# =====================================================================================

@router.get("/review/{review_id}")
async def review_detail(
    review_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Review).where(Review.id == review_id)
    rec = (await session.execute(stmt)).scalar_one_or_none()
    if not rec:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    return templates.TemplateResponse(
        "ui/review_detail.html",
        {"request": request, "rec": rec},
    )


@router.get("/reviews")
async def review_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: int | None = None,
):
    stmt = select(Review).order_by(Review.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(Review.user_id == user_id)

    rows = (await session.execute(stmt)).scalars().all()
    return templates.TemplateResponse(
        "ui/review_list.html",
        {"request": request, "rows": rows, "user_id": user_id},
    )


# =====================================================================================
# API 테스트 화면 (/ui/api-test)
# =====================================================================================

@router.get("/api-test")
async def api_test_form(request: Request):
    return templates.TemplateResponse(
        "ui/api_test.html",
        {"request": request, "resp": None},
    )


@router.post("/api-test")
async def api_test_submit(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Form(...),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
    token: str | None = Form(None),
    criteria: str | None = Form(None),
):
    # criteria 파싱
    if criteria:
        crit_list = [c.strip() for c in criteria.split(",") if c.strip()]
    else:
        crit_list = await _load_default_criteria(session)

    # LLM에 넘길 디버그용 payload (화면에서 보여줄 용도)
    llm_payload = {"code": code, "model": model_id, "criteria": crit_list}

    # 토큰 결정
    final_token: str | None = None
    access_cookie = request.cookies.get("access_token")

    if token:
        final_token = token
    elif access_cookie:
        final_token = access_cookie
    else:
        debug_url = f"http://localhost:8000/auth/github/debug/mint?user_id={user_id}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                debug_res = await client.get(debug_url)
            if debug_res.status_code == 200:
                data = debug_res.json()
                final_token = data.get("access_token")
        except Exception:
            final_token = None

    # ✅ /v1/reviews/request와 같은 포맷으로 생성
    payload = build_code_request_payload(
        user_id=int(user_id),
        model_id=model_id,
        language=language,
        trigger=trigger,
        code=code,
        aspects=crit_list,
    )

    url = "http://localhost:8000/v1/reviews/request"
    headers = {"Content-Type": "application/json"}

    if final_token:
        headers["Authorization"] = f"Bearer {final_token}"

    cookies = {}
    if access_cookie:
        cookies["access_token"] = access_cookie

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, headers=headers, cookies=cookies, json=payload)

    try:
        body = res.json()
    except Exception:
        body = {"raw": res.text}

    pretty_resp = json.dumps(body, ensure_ascii=False, indent=2)
    pretty_sent = json.dumps(payload, ensure_ascii=False, indent=2)
    llm_payload_pretty = json.dumps(llm_payload, ensure_ascii=False, indent=2)

    return templates.TemplateResponse(
        "ui/api_test.html",
        {
            "request": request,
            "resp": {"status": res.status_code, "json": body, "pretty": pretty_resp},
            "sent": payload,
            "sent_pretty": pretty_sent,
            "llm_payload_pretty": llm_payload_pretty,
            "used_authorization": bool(final_token),
        },
    )


# =====================================================================================
# 리뷰 로그
# =====================================================================================

@router.get("/review/{review_id}/logs")
async def review_logs(
    review_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(ActionLog)
        .where(ActionLog.event_name == "REVIEW_REQUEST")
        .order_by(ActionLog.timestamp.desc())
    )
    logs = (await session.execute(stmt)).scalars().all()

    return templates.TemplateResponse(
        "ui/review_logs.html",
        {"request": request, "review_id": review_id, "logs": logs},
    )

@router.get("/ws-debug")
async def ws_debug_page(request: Request):
    return templates.TemplateResponse("ui/ws_debug.html", {"request": request})
