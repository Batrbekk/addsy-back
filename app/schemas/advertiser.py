from pydantic import BaseModel


class AdvertiserListItem(BaseModel):
    id: str
    company_name: str | None = None
    logo_url: str | None = None
    industry: str | None = None
    city: str | None = None
    about: str | None = None
    rating: float = 0.0
    total_orders: int = 0
    total_spent: int = 0


class AdvertiserDetail(AdvertiserListItem):
    website: str | None = None
    review_breakdown: dict[str, int] = {}


class AdvertiserListResponse(BaseModel):
    data: list[AdvertiserListItem]
    meta: "PaginationMeta"


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
