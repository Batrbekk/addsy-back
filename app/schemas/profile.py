from pydantic import BaseModel, Field


class SetRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(creator|advertiser)$")


class CreatorSetupRequest(BaseModel):
    name: str
    bio: str | None = None
    city: str | None = None
    instagram: str | None = None
    tiktok: str | None = None
    categories: list[str] | None = None
    avatar_url: str | None = None


class AdvertiserSetupRequest(BaseModel):
    company_name: str
    industry: str | None = None
    city: str | None = None
    about: str | None = None
    website: str | None = None
    logo_url: str | None = None


class ProfileResponse(BaseModel):
    id: str
    phone: str
    role: str | None
    name: str | None
    avatar_url: str | None
    is_profile_complete: bool

    model_config = {"from_attributes": True}
