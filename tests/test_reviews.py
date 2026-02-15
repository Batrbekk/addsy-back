"""Tests for reviews endpoints."""
import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from tests.conftest import auth_headers


@pytest.fixture
async def completed_deal(db: AsyncSession, creator_user, advertiser_user, order):
    deal = Deal(
        id=uuid.uuid4(),
        order_id=order.id,
        offer_id=uuid.uuid4(),
        creator_id=creator_user.id,
        advertiser_id=advertiser_user.id,
        budget=100000,
        deadline=date(2026, 4, 1),
        status="completed",
        platform_fee=10000,
        creator_payout=90000,
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return deal


@pytest.mark.asyncio
async def test_create_review(client, creator_user, advertiser_user, completed_deal):
    resp = await client.post(
        "/v1/reviews",
        json={
            "deal_id": str(completed_deal.id),
            "user_id": str(creator_user.id),
            "rating": 5,
            "text": "Отличный креатор!",
        },
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rating"] == 5


@pytest.mark.asyncio
async def test_create_review_duplicate(client, creator_user, advertiser_user, completed_deal):
    await client.post(
        "/v1/reviews",
        json={
            "deal_id": str(completed_deal.id),
            "user_id": str(creator_user.id),
            "rating": 5,
            "text": "Первый",
        },
        headers=auth_headers(advertiser_user),
    )
    resp = await client.post(
        "/v1/reviews",
        json={
            "deal_id": str(completed_deal.id),
            "user_id": str(creator_user.id),
            "rating": 4,
            "text": "Второй",
        },
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_reviews(client, creator_user, advertiser_user, completed_deal):
    await client.post(
        "/v1/reviews",
        json={
            "deal_id": str(completed_deal.id),
            "user_id": str(creator_user.id),
            "rating": 5,
            "text": "Круто!",
        },
        headers=auth_headers(advertiser_user),
    )
    resp = await client.get(f"/v1/reviews/{creator_user.id}", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["total_count"] == 1
    assert data["summary"]["average_rating"] == 5.0
    assert len(data["data"]) == 1
