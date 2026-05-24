from pydantic import BaseModel, Field
from typing import Optional

class JwtLoginRequest(BaseModel):
    phone: str = Field(..., alias="phone")
    pin: str = Field(..., alias="pin")

    class Config:
        populate_by_name = True

class JwtRefreshRequest(BaseModel):
    refresh_token: str = Field(..., alias="refreshToken")

    class Config:
        populate_by_name = True

class JwtTokenResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    refresh_token: Optional[str] = Field(default=None, alias="refreshToken")
    user_id: str = Field(alias="userId")

    class Config:
        populate_by_name = True
