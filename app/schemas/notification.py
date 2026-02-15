from datetime import datetime

from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: str
    type: str
    title: str
    body: str
    is_read: bool = False
    reference_type: str | None = None
    reference_id: str | None = None
    created_at: datetime


class NotificationMeta(BaseModel):
    page: int
    total: int
    unread_count: int = 0


class NotificationListResponse(BaseModel):
    data: list[NotificationItem]
    meta: NotificationMeta


class MarkReadResponse(BaseModel):
    id: str
    is_read: bool = True


class MarkAllReadResponse(BaseModel):
    updated_count: int
