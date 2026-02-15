import os
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.chat import Chat, Message, Offer  # noqa: F401
from app.models.deal import Deal, DealSignature, SubmittedWork, WorkRequirement  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.order import Order
from app.models.otp import OTPCode  # noqa: F401
from app.models.response import Response  # noqa: F401
from app.models.review import Review  # noqa: F401
from app.models.user import AdvertiserProfile, CreatorProfile, User

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://batyrbekkuandyk@localhost:5432/addsy_test",
)


@pytest_asyncio.fixture
async def db():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def client(db):
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def creator_user(db: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        phone="+77001112233",
        role="creator",
        name="Test Creator",
        is_profile_complete=True,
    )
    db.add(user)
    profile = CreatorProfile(
        user_id=user.id,
        bio="Test bio",
        city="Алматы",
        categories=["lifestyle", "tech"],
        followers_count=5000,
        rating=4.5,
        reviews_count=10,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def advertiser_user(db: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        phone="+77009998877",
        role="advertiser",
        name="Test Advertiser",
        is_profile_complete=True,
    )
    db.add(user)
    profile = AdvertiserProfile(
        user_id=user.id,
        company_name="TestCorp",
        industry="fintech",
        city="Астана",
        rating=4.8,
        total_orders=5,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def order(db: AsyncSession, advertiser_user: User):
    o = Order(
        id=uuid.uuid4(),
        advertiser_id=advertiser_user.id,
        title="Тестовый заказ",
        description="Описание тестового заказа",
        budget=100000,
        currency="KZT",
        deadline=date(2026, 4, 1),
        platform="instagram",
        content_type="video",
        content_count=2,
        categories=["lifestyle"],
        city="Алматы",
    )
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return o


@pytest_asyncio.fixture
async def chat(db: AsyncSession, creator_user: User, advertiser_user: User, order: Order):
    c = Chat(
        id=uuid.uuid4(),
        participant_1=advertiser_user.id,
        participant_2=creator_user.id,
        order_id=order.id,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c
