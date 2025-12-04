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

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def parse_state(raw_state: str):
  """
  raw_state 예:
    - "web:http://localhost:3000"
    - "signup:https://web-dkmv.vercel.app"
    - "extension:https://web-dkmv.vercel.app"
    - "native"
  """
  if not raw_state:
      return "web", None

  if ":" not in raw_state:
      return raw_state, None

  flow, origin = raw_state.split(":", 1)
  return flow, origin


@router.get("/login")
async def gh_login(state: str = "web"):
    url = github_login_url(state)
    return RedirectResponse(url=url, status_code=303)


@router.get("/callback")
async def gh_callback(
    code: str,
    state: str = "native",
    session: AsyncSession = Depends(get_session),
):

    flow, origin = parse_state(state)

    access_token = await exchange_code_for_token(code)

    me = await fetch_github_me(access_token)

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

    token = create_jwt(user.id)

    if flow == "native":
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


    if flow == "extension":
        vs_uri = f"vscode://rockcha.dkmv/callback?token={token}"
        return RedirectResponse(url=vs_uri, status_code=303)


    frontend_base = FRONTEND_URL

    if origin:
        frontend_base = origin.rstrip("/")

    status = "new" if is_new_user else "existing"
    redirect_url = (
        f"{frontend_base}/auth/github/callback"
        f"?token={token}&status={status}"
    )
    return RedirectResponse(url=redirect_url, status_code=303)


def get_current_user_id(request: Request) -> int:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = decode_jwt(auth.split(" ", 1)[1])
    return int(payload["sub"])


def get_current_user_id_from_cookie(request: Request) -> int:

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
    resp = RedirectResponse(url="/ui/reviews", status_code=303)
    resp.delete_cookie("access_token", path="/")
    return resp


@router.get("/debug/mint")
def mint_debug_token(user_id: int):
    return {"token": create_jwt(user_id)}


@router.post("/vscode/token")
async def mint_vscode_token(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_jwt(user.id)
    return {"token": token}
