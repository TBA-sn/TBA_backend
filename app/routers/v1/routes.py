from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils.deps import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "pong"}

@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    u = User(email=payload.email, nickname=payload.nickname)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()
