"""Tests for orders endpoints."""
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_order(client, advertiser_user):
    resp = await client.post(
        "/v1/orders",
        json={
            "title": "Нужен обзор",
            "description": "UGC обзор приложения",
            "budget": 150000,
            "deadline": "2026-05-01",
            "platform": "tiktok",
            "content_type": "video",
        },
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Нужен обзор"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_order_forbidden_for_creator(client, creator_user):
    resp = await client.post(
        "/v1/orders",
        json={
            "title": "test",
            "description": "test",
            "budget": 100000,
            "deadline": "2026-05-01",
            "platform": "instagram",
            "content_type": "video",
        },
        headers=auth_headers(creator_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_orders(client, creator_user, order):
    resp = await client.get("/v1/orders", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["title"] == "Тестовый заказ"


@pytest.mark.asyncio
async def test_list_orders_text_search(client, creator_user, order):
    resp = await client.get("/v1/orders?q=Тестовый", headers=auth_headers(creator_user))
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/orders?q=Несуществующий", headers=auth_headers(creator_user))
    assert len(resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_list_orders_filter_budget(client, creator_user, order):
    resp = await client.get("/v1/orders?min_budget=50000&max_budget=200000", headers=auth_headers(creator_user))
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/orders?min_budget=200000", headers=auth_headers(creator_user))
    assert len(resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_get_order_detail(client, creator_user, order):
    resp = await client.get(f"/v1/orders/{order.id}", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Тестовый заказ"


@pytest.mark.asyncio
async def test_my_orders(client, advertiser_user, order):
    resp = await client.get("/v1/orders/my", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
