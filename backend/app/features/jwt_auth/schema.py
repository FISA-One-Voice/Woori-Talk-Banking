from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JwtLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    phone: str = Field(..., alias="phone")
    pin: str = Field(..., alias="pin")


class JwtRefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(..., alias="refreshToken")


class JwtTokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(alias="accessToken")
    refresh_token: Optional[str] = Field(default=None, alias="refreshToken")
    user_id: str = Field(alias="userId")
    has_voice_registered: bool = Field(default=False, alias="hasVoiceRegistered")

