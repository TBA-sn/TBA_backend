# app/routers/v1/user.py (요지)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.utils.database import get_session
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/v1/users", tags=["user"])

@router.post("", response_model=UserOut)
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session)):
    u = User(
        github_id=payload.github_id,
        login=payload.login,
        name=payload.name,
        avatar_url=payload.avatar_url,
    )
    session.add(u)
    await session.flush()
    await session.commit()
    return u

@router.get("", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return rows
