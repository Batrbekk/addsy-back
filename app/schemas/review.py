from datetime import datetime

from pydantic import BaseModel, Field


class ReviewerBrief(BaseModel):
    id: str
    name: str | None = None
    avatar_url: str | None = None
    role: str | None = None


class ReviewItem(BaseModel):
    id: str
    reviewer: ReviewerBrief
    rating: int
    text: str | None = None
    order_title: str | None = None
    deal_id: str | None = None
    created_at: datetime


class ReviewSummary(BaseModel):
    average_rating: float = 0.0
    total_count: int = 0
    breakdown: dict[str, int] = {}


class ReviewListResponse(BaseModel):
    summary: ReviewSummary
    data: list[ReviewItem]
    meta: "ReviewMeta"


class ReviewMeta(BaseModel):
    page: int
    total: int


class CreateReviewRequest(BaseModel):
    deal_id: str
    user_id: str
    rating: int = Field(..., ge=1, le=5)
    text: str | None = None


class CreateReviewResponse(BaseModel):
    id: str
    rating: int
    text: str | None = None
    created_at: datetime
