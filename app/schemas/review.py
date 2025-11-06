from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ExtensionRequest(BaseModel):
    user_id: str
    model_id: str
    code: str
    language: str
    trigger: str

class LLMRequest(BaseModel):
    code: str
    model: str
    criteria: List[str] = Field(default_factory=lambda: ["readability","efficiency","consistency"])

class CategoryDetail(BaseModel):
    name: str
    score: int
    comment: Optional[str] = None

class LLMResponse(BaseModel):
    scores: Dict[str, int] 
    categories: List[CategoryDetail]
    summary: str

class CategoryOut(BaseModel):
    name: str
    score: int
    comment: str | None = None

class ReviewOut(BaseModel):
    review_id: int | str
    global_score: int
    model_score: int
    categories: List[CategoryOut]
    summary: str

class LogCreate(BaseModel):
    log_id: str
    user_id: str
    case_id: str
    action: str

CodeRequest = ExtensionRequest