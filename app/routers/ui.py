# app/routers/ui.py
from uuid import uuid4
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_session
from app.models.review import Review
from app.models.action_log import ActionLog
from app.models.user import User
from app.routers.auth import get_current_user_id_from_cookie
import httpx
import os

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/templates")

INTERNAL_API_BASE: str = os.getenv("INTERNAL_API_BASE", "http://127.0.0.1:8000")


async def _get_current_user(
    request: Request,
    session: AsyncSession,
) -> Optional[User]:
    try:
        uid = get_current_user_id_from_cookie(request)
    except Exception:
        return None

    if not uid:
        return None

    row = await session.execute(select(User).where(User.id == uid))
    return row.scalar_one_or_none()


def build_code_request_payload(
    *,
    user_id: int,
    model_id: str,
    language: str,
    trigger: str,
    code: str,
    aspects: List[str],
) -> dict:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    meta = {
        "version": "v1",
        "ts": now,
        "correlation_id": str(uuid4()),
        "actor": "web",
        "code_fingerprint": None,
        "model": {"name": model_id},
        "analysis": {"aspects": aspects, "total_steps": 6},
        "progress": {"status": "pending", "next_step": 1},
        "result": None,
        "audit": None,
    }

    body = {
        "user_id": user_id,
        "snippet": {
            "code": code,
            "language": language,
        },
        "trigger": trigger,
        "model": model_id,
    }

    return {"meta": meta, "body": body}


# =====================================================================
# 리뷰 폼
# =====================================================================

@router.get("/review")
async def review_form(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_current_user(request, session)

    ctx = {
        "request": request,
        "current_user_id": user.id if user else None,
        "current_user_login": user.login if user else None,
    }
    return templates.TemplateResponse("ui/review_form.html", ctx)


@router.post("/review")
async def review_submit(
    request: Request,
    user_id: int | None = Form(None),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
):
    try:
        uid = get_current_user_id_from_cookie(request)
    except Exception:
        uid = None

    if uid is None:
        uid = user_id

    if uid is None:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    criteria: List[str] = []

    payload = build_code_request_payload(
        user_id=int(uid),
        model_id=model_id,
        language=language,
        trigger=trigger,
        code=code,
        aspects=criteria,
    )

    url = f"{INTERNAL_API_BASE}/v1/reviews/request"

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, json=payload)

    if res.status_code != 200:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    body = res.json()
    resp_body = body.get("body") or {}
    review_id = resp_body.get("review_id")

    if not review_id:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    return RedirectResponse(url=f"/ui/review/{review_id}", status_code=303)


# =====================================================================
# 리뷰 상세 / 목록
# =====================================================================

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

    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/review_detail.html",
        {
            "request": request,
            "rec": rec,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
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
    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/review_list.html",
        {
            "request": request,
            "rows": rows,
            "user_id": user_id,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


# =====================================================================
# API 테스트 화면 (/ui/api-test)
# =====================================================================

@router.get("/api-test")
async def api_test_form(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/api_test.html",
        {
            "request": request,
            "resp": None,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


@router.post("/api-test")
async def api_test_submit(
    request: Request,
    user_id: str = Form(""),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
    token: str | None = Form(None),
    criteria: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_current_user(request, session)
    effective_user_id: Optional[int] = None

    if user:
        effective_user_id = user.id
    elif user_id:
        effective_user_id = int(user_id)

    if effective_user_id is None:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    if criteria:
        crit_list = [c.strip() for c in criteria.split(",") if c.strip()]
    else:
        crit_list = []

    llm_payload = {
        "code": code,
        "model": model_id,
        "criteria": crit_list,
    }

    final_token: str | None = None
    access_cookie = request.cookies.get("access_token")

    if token:
        final_token = token
    elif access_cookie:
        final_token = access_cookie
    else:
        debug_url = f"{INTERNAL_API_BASE}/auth/github/debug/mint?user_id={effective_user_id}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                debug_res = await client.get(debug_url)
            if debug_res.status_code == 200:
                data = debug_res.json()
                final_token = data.get("body", {}).get("access_token")
        except Exception:
            final_token = None

    payload = build_code_request_payload(
        user_id=effective_user_id,
        model_id=model_id,
        language=language,
        trigger=trigger,
        code=code,
        aspects=crit_list,
    )

    url = f"{INTERNAL_API_BASE}/v1/reviews/request"
    headers = {"Content-Type": "application/json"}

    if final_token:
        headers["Authorization"] = f"Bearer {final_token}"

    cookies = {}
    if access_cookie:
        cookies["access_token"] = access_cookie

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, headers=headers, cookies=cookies, json=payload)
        try:
            body = res.json()
        except Exception:
            body = {"raw": res.text}
        status = res.status_code
    except httpx.ReadTimeout:
        res = None
        body = {
            "error": "ReadTimeout: /v1/reviews/request 응답이 너무 오래 걸렸습니다."
        }
        status = 504

    pretty_resp = json.dumps(body, ensure_ascii=False, indent=2)
    pretty_sent = json.dumps(payload, ensure_ascii=False, indent=2)
    llm_payload_pretty = json.dumps(llm_payload, ensure_ascii=False, indent=2)

    return templates.TemplateResponse(
        "ui/api_test.html",
        {
            "request": request,
            "resp": {"status": status, "json": body, "pretty": pretty_resp},
            "sent": payload,
            "sent_pretty": pretty_sent,
            "llm_payload_pretty": llm_payload_pretty,
            "used_authorization": bool(final_token),
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


# =====================================================================
# 리뷰 로그
# =====================================================================

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

    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/review_logs.html",
        {
            "request": request,
            "review_id": review_id,
            "logs": logs,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


@router.get("/ws-debug")
async def ws_debug_page(request: Request):
    return templates.TemplateResponse("ui/ws_debug.html", {"request": request})
