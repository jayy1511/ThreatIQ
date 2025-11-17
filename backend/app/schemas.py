from pydantic import BaseModel, EmailStr
from enum import Enum
from datetime import datetime

class RoleEnum(str, Enum):
    user = "user"
    admin = "admin"

class RegisterIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleEnum

# For returning analysis history
class AnalysisOut(BaseModel):
    id: int
    text: str
    sender: str | None
    result: dict
    created_at: datetime

    class Config:
        from_attributes = True
