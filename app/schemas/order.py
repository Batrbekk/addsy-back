from datetime import date, datetime

from pydantic import BaseModel


class AdvertiserBrief(BaseModel):
    id: str
    company_name: str | None = None
    logo_url: str | None = None
    rating: float | None = None


class OrderListItem(BaseModel):
    id: str
    advertiser: AdvertiserBrief
    title: str
    description: str
    budget: int
    currency: str = "KZT"
    deadline: date
    platform: str
    content_type: str
    content_count: int = 1
    content_duration_min: int | None = None
    content_duration_max: int | None = None
    categories: list[str] | None = None
    city: str | None = None
    status: str
    response_count: int = 0
    created_at: datetime


class OrderDetail(OrderListItem):
    my_response: dict | None = None


class OrderCreateRequest(BaseModel):
    title: str
    description: str
    budget: int
    currency: str = "KZT"
    deadline: date
    platform: str
    content_type: str
    content_count: int = 1
    content_duration_min: int | None = None
    content_duration_max: int | None = None
    categories: list[str] | None = None
    city: str | None = None


class OrderCreateResponse(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime


class CreatorBrief(BaseModel):
    id: str
    name: str | None = None
    username: str | None = None
    avatar_url: str | None = None


class MyOrderItem(BaseModel):
    id: str
    title: str
    budget: int
    currency: str = "KZT"
    status: str
    response_count: int = 0
    selected_creator: CreatorBrief | None = None
    created_at: datetime


class OrderListResponse(BaseModel):
    data: list[OrderListItem]
    meta: "PaginationMeta"


class MyOrderListResponse(BaseModel):
    data: list[MyOrderItem]
    meta: "PaginationMeta"


class PaginationMeta(BaseModel):
    page: int
    per_page: int = 20
    total: int
    total_pages: int = 0
