"""Tests for offers endpoints: my/sent, my/received, view, cancel."""
import pytest

from tests.conftest import auth_headers


async def _send_offer(client, advertiser_user, chat, order):
    resp = await client.post(
        f"/v1/chats/{chat.id}/offer",
        json={
            "order_id": str(order.id),
            "budget": 100000,
            "deadline": "2026-04-15T00:00:00Z",
            "conditions": "Test conditions",
            "video_count": 1,
        },
        headers=auth_headers(advertiser_user),
    )
    return resp.json()["offer"]["id"]


@pytest.mark.asyncio
async def test_my_sent_offers(client, advertiser_user, creator_user, chat, order):
    await _send_offer(client, advertiser_user, chat, order)

    resp = await client.get("/v1/offers/my/sent", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["status"] == "pending"
    assert data["data"][0]["budget"] == 100000


@pytest.mark.asyncio
async def test_my_received_offers(client, advertiser_user, creator_user, chat, order):
    await _send_offer(client, advertiser_user, chat, order)

    resp = await client.get("/v1/offers/my/received", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["sender"]["name"] == "Test Advertiser"


@pytest.mark.asyncio
async def test_my_sent_offers_filter_status(client, advertiser_user, creator_user, chat, order):
    await _send_offer(client, advertiser_user, chat, order)

    resp = await client.get("/v1/offers/my/sent?status=pending", headers=auth_headers(advertiser_user))
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/offers/my/sent?status=accepted", headers=auth_headers(advertiser_user))
    assert len(resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_view_offer(client, advertiser_user, creator_user, chat, order):
    offer_id = await _send_offer(client, advertiser_user, chat, order)

    resp = await client.post(f"/v1/offers/{offer_id}/view", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "viewed"
    assert data["viewed_at"] is not None


@pytest.mark.asyncio
async def test_cancel_offer(client, advertiser_user, creator_user, chat, order):
    offer_id = await _send_offer(client, advertiser_user, chat, order)

    resp = await client.post(f"/v1/offers/{offer_id}/cancel", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_offer_already_accepted(client, advertiser_user, creator_user, chat, order):
    offer_id = await _send_offer(client, advertiser_user, chat, order)

    # Accept first
    await client.post(
        f"/v1/chats/{chat.id}/offer/{offer_id}/respond",
        json={"action": "accept"},
        headers=auth_headers(creator_user),
    )

    # Try cancel
    resp = await client.post(f"/v1/offers/{offer_id}/cancel", headers=auth_headers(advertiser_user))
    assert resp.status_code == 400
