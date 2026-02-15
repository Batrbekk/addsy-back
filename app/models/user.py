import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_profile_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator_profile: Mapped["CreatorProfile"] = relationship(back_populates="user", uselist=False)
    advertiser_profile: Mapped["AdvertiserProfile"] = relationship(back_populates="user", uselist=False)


class CreatorProfile(Base):
    __tablename__ = "creator_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="Казахстан")
    instagram: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tiktok: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categories: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    followers_count: Mapped[int] = mapped_column(default=0)
    average_reach: Mapped[int] = mapped_column(default=0)
    rating: Mapped[float] = mapped_column(default=0.0)
    reviews_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="creator_profile")


class AdvertiserProfile(Base):
    __tablename__ = "advertiser_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    about: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_orders: Mapped[int] = mapped_column(default=0)
    rating: Mapped[float] = mapped_column(default=0.0)
    total_spent: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="advertiser_profile")
