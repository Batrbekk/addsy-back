"""Tests for chats endpoints."""
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_chat(client, creator_user, advertiser_user):
    resp = await client.post(
        "/v1/chats",
        json={"participant_id": str(creator_user.id)},
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["participant"]["name"] == "Test Creator"


@pytest.mark.asyncio
async def test_create_chat_duplicate_returns_existing(client, creator_user, advertiser_user):
    resp1 = await client.post(
        "/v1/chats",
        json={"participant_id": str(creator_user.id)},
        headers=auth_headers(advertiser_user),
    )
    resp2 = await client.post(
        "/v1/chats",
        json={"participant_id": str(creator_user.id)},
        headers=auth_headers(advertiser_user),
    )
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
async def test_list_chats(client, creator_user, advertiser_user, chat):
    resp = await client.get("/v1/chats", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_send_message(client, advertiser_user, chat):
    resp = await client.post(
        f"/v1/chats/{chat.id}/messages",
        json={"content": "Привет!"},
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 201
    assert resp.json()["content"] == "Привет!"


@pytest.mark.asyncio
async def test_get_messages(client, advertiser_user, chat):
    await client.post(
        f"/v1/chats/{chat.id}/messages",
        json={"content": "Сообщение 1"},
        headers=auth_headers(advertiser_user),
    )
    await client.post(
        f"/v1/chats/{chat.id}/messages",
        json={"content": "Сообщение 2"},
        headers=auth_headers(advertiser_user),
    )
    resp = await client.get(f"/v1/chats/{chat.id}/messages", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_send_offer(client, advertiser_user, chat, order):
    resp = await client.post(
        f"/v1/chats/{chat.id}/offer",
        json={
            "order_id": str(order.id),
            "budget": 120000,
            "deadline": "2026-04-15T00:00:00Z",
            "conditions": "2 видео по 60 сек",
            "start_date": "2026-03-01",
            "end_date": "2026-04-01",
            "video_count": 2,
            "content_description": "Обзор приложения",
        },
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["offer"]["budget"] == 120000
    assert data["offer"]["video_count"] == 2
    assert data["offer"]["conditions"] == "2 видео по 60 сек"
    assert data["offer"]["status"] == "pending"


@pytest.mark.asyncio
async def test_respond_offer_accept(client, creator_user, advertiser_user, chat, order):
    # Send offer
    offer_resp = await client.post(
        f"/v1/chats/{chat.id}/offer",
        json={
            "order_id": str(order.id),
            "budget": 120000,
            "deadline": "2026-04-15T00:00:00Z",
            "video_count": 2,
        },
        headers=auth_headers(advertiser_user),
    )
    offer_id = offer_resp.json()["offer"]["id"]

    # Accept
    resp = await client.post(
        f"/v1/chats/{chat.id}/offer/{offer_id}/respond",
        json={"action": "accept"},
        headers=auth_headers(creator_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["deal_id"] is not None


@pytest.mark.asyncio
async def test_respond_offer_decline(client, creator_user, advertiser_user, chat, order):
    offer_resp = await client.post(
        f"/v1/chats/{chat.id}/offer",
        json={
            "order_id": str(order.id),
            "budget": 120000,
            "deadline": "2026-04-15T00:00:00Z",
        },
        headers=auth_headers(advertiser_user),
    )
    offer_id = offer_resp.json()["offer"]["id"]

    resp = await client.post(
        f"/v1/chats/{chat.id}/offer/{offer_id}/respond",
        json={"action": "decline"},
        headers=auth_headers(creator_user),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"
    assert resp.json()["deal_id"] is None
