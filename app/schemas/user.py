from typing import Optional
from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
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
    store_code: bool
    model_config = ConfigDict(from_attributes=True)

class UserStoreCodeUpdate(BaseModel):
    store_code: bool





# 사랑해