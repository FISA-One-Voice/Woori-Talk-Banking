from pydantic import BaseModel
from typing import Optional

class JwtLoginRequest(BaseModel):
    user_id: str

class JwtRefreshRequest(BaseModel):
    refresh_token: str

class JwtTokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    user_id: str
