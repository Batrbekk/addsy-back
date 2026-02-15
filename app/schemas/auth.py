from pydantic import BaseModel, Field


class SendOTPRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+7\d{10}$", examples=["+77771234567"])


class SendOTPResponse(BaseModel):
    message: str = "OTP sent"


class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+7\d{10}$")
    code: str = Field(..., min_length=6, max_length=6)


class VerifyOTPResponse(BaseModel):
    token: str
    refresh_token: str
    user: "UserBrief"


class UserBrief(BaseModel):
    id: str
    phone: str
    role: str | None
    name: str | None
    avatar_url: str | None
    is_profile_complete: bool

    model_config = {"from_attributes": True}


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    token: str
    refresh_token: str


class ErrorResponse(BaseModel):
    message: str
