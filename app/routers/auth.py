# app/routers/auth.py
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.responses import RedirectResponse

from app.utils.database import get_session
from app.models.user import User

from app.services.auth import (
    github_login_url,
    exchange_code_for_token,
    fetch_github_me,
    create_jwt,
    decode_jwt,
)

router = APIRouter(prefix="/auth/github", tags=["auth"])

# ✅ FRONTEND_URL 끝에 / 안 붙게 정리
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


@router.get("/login")
async def gh_login(state: str = "web"):
    """
    GitHub 로그인 시작
    - state="native": 백엔드 UI(/ui/reviews)에서 사용하는 로그인
    - state="web": 프론트엔드에서 사용하는 로그인 (로그인 후 프론트로 리다이렉트)
    - 그 외: 기본적으로 프론트 플로우로 처리
    """
    # ✅ 여기서 받은 state를 그대로 GitHub authorize URL에 실어 보냄
    url = github_login_url(state)
    return RedirectResponse(url=url, status_code=303)


@router.get("/callback")
async def gh_callback(
    code: str,
    state: str = "native",
    session: AsyncSession = Depends(get_session),
):
    """
    GitHub OAuth 콜백
    - GitHub access_token 교환
    - /user 정보 가져와서 User 테이블 upsert
    - JWT 발급
      * state="native"  → access_token 쿠키에 심고 /ui/reviews로 리다이렉트
      * state!="native" → FRONTEND_URL/auth/github/callback?token=...&status=new|existing 으로 리다이렉트
    """
    # 1) GitHub access_token 교환
    access_token = await exchange_code_for_token(code)

    # 2) /user 정보 가져오기
    me = await fetch_github_me(access_token)

    # 3) User 테이블 upsert + 신규/기존 여부 판단
    q = await session.execute(select(User).where(User.github_id == str(me["id"])))
    user = q.scalar_one_or_none()

    is_new_user = False
    if not user:
        is_new_user = True
        user = User(
            github_id=str(me["id"]),
            login=me.get("login", ""),
            name=me.get("name"),
            avatar_url=me.get("avatar_url"),
        )
        session.add(user)
        await session.flush()

    await session.commit()

    # 4) JWT 발급 (sub = user.id)
    token = create_jwt(user.id)

    # 🔀 분기: native ↔ web
    if state == "native":
        # ✅ 백엔드 UI에서 쓰는 로그인 플로우
        resp = RedirectResponse(url="/ui/reviews", status_code=303)
        resp.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=60 * 60 * 24 * 7,
            path="/",
        )
        return resp

    # ✅ 그 외(state="web", "signup" 등)는 모두 프론트로 리다이렉트
    #    - status=new      : 처음 가입한 GitHub 계정
    #    - status=existing : 이미 DKMV에 존재하는 GitHub 계정
    status = "new" if is_new_user else "existing"
    redirect_url = f"{FRONTEND_URL}/auth/github/callback?token={token}&status={status}"
    return RedirectResponse(url=redirect_url, status_code=303)


def get_current_user_id(request: Request) -> int:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = decode_jwt(auth.split(" ", 1)[1])
    return int(payload["sub"])


def get_current_user_id_from_cookie(request: Request) -> int:
    """
    Authorization 헤더의 Bearer 토큰 또는 access_token 쿠키에서 user_id 추출
    """
    auth = request.headers.get("Authorization", "")
    token = None

    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    else:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(401, "missing token (cookie or bearer)")

    payload = decode_jwt(token)
    return int(payload["sub"])


@router.get("/logout")
@router.post("/logout")
async def logout():
    # 이건 백엔드 UI(/ui/reviews)용 로그아웃
    resp = RedirectResponse(url="/ui/reviews", status_code=303)
    resp.delete_cookie("access_token", path="/")
    return resp


@router.get("/debug/mint")
def mint_debug_token(user_id: int):
    return {"token": create_jwt(user_id)}
