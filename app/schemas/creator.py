from pydantic import BaseModel


class CreatorSocials(BaseModel):
    instagram: str | None = None
    tiktok: str | None = None


class CreatorListItem(BaseModel):
    id: str
    name: str | None
    username: str | None = None
    avatar_url: str | None
    bio: str | None = None
    city: str | None = None
    categories: list[str] | None = None
    followers_count: int = 0
    average_reach: int = 0
    rating: float = 0.0
    reviews_count: int = 0
    socials: CreatorSocials | None = None


class PortfolioItem(BaseModel):
    id: str
    thumbnail_url: str | None = None
    type: str = "image"


class CreatorDetail(CreatorListItem):
    country: str | None = None
    portfolio: list[PortfolioItem] = []
    review_breakdown: dict[str, int] = {}


class CreatorListResponse(BaseModel):
    data: list[CreatorListItem]
    meta: "PaginationMeta"


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
