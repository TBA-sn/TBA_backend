 # app/schemas/user.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class UserBase(BaseModel):
    github_id: Optional[str] = None
    login: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(BaseModel):
    github_id: str
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserOut(BaseModel):
    id: int
    github_id: str
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None


# 사랑해