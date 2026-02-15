from datetime import date, datetime

from pydantic import BaseModel


class OfferOrderBrief(BaseModel):
    id: str
    title: str


class OfferParticipant(BaseModel):
    id: str
    name: str | None = None
    avatar_url: str | None = None
    company_name: str | None = None


class OfferListItem(BaseModel):
    id: str
    order: OfferOrderBrief
    sender: OfferParticipant
    recipient: OfferParticipant
    budget: int
    currency: str = "KZT"
    deadline: str
    conditions: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    video_count: int | None = None
    content_description: str | None = None
    status: str
    viewed_at: datetime | None = None
    created_at: datetime


class OfferListResponse(BaseModel):
    data: list[OfferListItem]
    meta: "PaginationMeta"


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class OfferCancelResponse(BaseModel):
    id: str
    status: str = "cancelled"


class OfferViewResponse(BaseModel):
    id: str
    status: str
    viewed_at: datetime
