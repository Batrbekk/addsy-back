"""Tests for responses endpoints."""
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_response(client, creator_user, order):
    resp = await client.post(
        f"/v1/orders/{order.id}/responses",
        json={"message": "Готов сделать!", "proposed_price": 90000},
        headers=auth_headers(creator_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "reviewing"


@pytest.mark.asyncio
async def test_create_response_duplicate(client, creator_user, order):
    await client.post(
        f"/v1/orders/{order.id}/responses",
        json={"message": "Первый"},
        headers=auth_headers(creator_user),
    )
    resp = await client.post(
        f"/v1/orders/{order.id}/responses",
        json={"message": "Второй"},
        headers=auth_headers(creator_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_my_responses(client, creator_user, order):
    await client.post(
        f"/v1/orders/{order.id}/responses",
        json={"message": "Готов"},
        headers=auth_headers(creator_user),
    )
    resp = await client.get("/v1/orders/my/responses", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_order_responses_as_advertiser(client, creator_user, advertiser_user, order):
    await client.post(
        f"/v1/orders/{order.id}/responses",
        json={"message": "Готов"},
        headers=auth_headers(creator_user),
    )
    resp = await client.get(f"/v1/orders/{order.id}/responses", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["creator"]["name"] == "Test Creator"
