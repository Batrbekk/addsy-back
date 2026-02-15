from datetime import date, datetime

from pydantic import BaseModel


class ParticipantBrief(BaseModel):
    id: str
    name: str | None = None
    avatar_url: str | None = None
    role: str | None = None
    is_online: bool = False


class LastMessage(BaseModel):
    content: str
    type: str = "text"
    created_at: datetime


class ChatListItem(BaseModel):
    id: str
    participant: ParticipantBrief
    last_message: LastMessage | None = None
    unread_count: int = 0
    order_id: str | None = None
    updated_at: datetime


class ChatListResponse(BaseModel):
    data: list[ChatListItem]


class CreateChatRequest(BaseModel):
    participant_id: str
    order_id: str | None = None


class CreateChatResponse(BaseModel):
    id: str
    participant: ParticipantBrief
    order_id: str | None = None


class MessageItem(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    type: str = "text"
    content: str
    created_at: datetime
    read_at: datetime | None = None


class MessageListResponse(BaseModel):
    data: list[MessageItem]
    has_more: bool = False


class SendMessageRequest(BaseModel):
    type: str = "text"
    content: str


class SendOfferRequest(BaseModel):
    order_id: str
    budget: int
    deadline: datetime
    content_description: str | None = None
    conditions: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    video_count: int | None = None


class OfferBrief(BaseModel):
    id: str
    order_title: str | None = None
    budget: int
    currency: str = "KZT"
    deadline: str
    content_description: str | None = None
    conditions: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    video_count: int | None = None
    status: str = "pending"


class OfferMessageResponse(BaseModel):
    id: str
    chat_id: str
    type: str = "offer"
    offer: OfferBrief
    created_at: datetime


class RespondOfferRequest(BaseModel):
    action: str  # "accept" or "decline"


class RespondOfferResponse(BaseModel):
    offer_id: str
    status: str
    deal_id: str | None = None
