from datetime import datetime

from pydantic import BaseModel


class CreateResponseRequest(BaseModel):
    message: str | None = None
    proposed_price: int | None = None


class ResponseCreated(BaseModel):
    id: str
    order_id: str
    status: str
    created_at: datetime


class OrderBrief(BaseModel):
    id: str
    title: str
    advertiser: "AdvertiserBrief"
    budget: int
    currency: str = "KZT"


class AdvertiserBrief(BaseModel):
    company_name: str | None = None
    logo_url: str | None = None


class CreatorBrief(BaseModel):
    id: str
    name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    rating: float | None = None
    categories: list[str] | None = None


class MyResponseItem(BaseModel):
    id: str
    order: OrderBrief
    status: str
    created_at: datetime


class OrderResponseItem(BaseModel):
    id: str
    creator: CreatorBrief
    message: str | None = None
    proposed_price: int | None = None
    status: str
    created_at: datetime


class MyResponsesListResponse(BaseModel):
    data: list[MyResponseItem]


class OrderResponsesListResponse(BaseModel):
    data: list[OrderResponseItem]
