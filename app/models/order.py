import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertiser_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="KZT")
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_count: Mapped[int] = mapped_column(Integer, default=1)
    content_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_duration_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    categories: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    response_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
