"""Tests for the full deal flow: offer → sign → pay → work → confirm/dispute."""
import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import auth_headers


async def _create_deal(client, advertiser_user, creator_user, chat, order):
    """Helper: send offer + accept → returns deal_id."""
    offer_resp = await client.post(
        f"/v1/chats/{chat.id}/offer",
        json={
            "order_id": str(order.id),
            "budget": 100000,
            "deadline": "2026-04-15T00:00:00Z",
            "conditions": "2 видео по 60 сек",
            "start_date": "2026-03-01",
            "end_date": "2026-04-01",
            "video_count": 2,
        },
        headers=auth_headers(advertiser_user),
    )
    offer_id = offer_resp.json()["offer"]["id"]

    accept_resp = await client.post(
        f"/v1/chats/{chat.id}/offer/{offer_id}/respond",
        json={"action": "accept"},
        headers=auth_headers(creator_user),
    )
    return accept_resp.json()["deal_id"]


# ────────────────────────────────────────
# DEAL CREATION
# ────────────────────────────────────────

@pytest.mark.asyncio
async def test_deal_created_on_accept(client, advertiser_user, creator_user, chat, order):
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)
    assert deal_id is not None

    # Check deal detail
    resp = await client.get(f"/v1/deals/{deal_id}", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "contract_pending"
    assert data["budget"] == 100000
    assert data["video_count"] == 2
    assert data["conditions"] == "2 видео по 60 сек"


@pytest.mark.asyncio
async def test_list_deals(client, advertiser_user, creator_user, chat, order):
    await _create_deal(client, advertiser_user, creator_user, chat, order)

    resp = await client.get("/v1/deals", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/deals", headers=auth_headers(creator_user))
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_list_deals_filter_status(client, advertiser_user, creator_user, chat, order):
    await _create_deal(client, advertiser_user, creator_user, chat, order)

    resp = await client.get("/v1/deals?status=contract_pending", headers=auth_headers(advertiser_user))
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/deals?status=in_progress", headers=auth_headers(advertiser_user))
    assert len(resp.json()["data"]) == 0


# ────────────────────────────────────────
# CONTRACT SIGNING
# ────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_sign_sends_sms(client, advertiser_user, creator_user, chat, order):
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)

    with patch("app.routers.deals.send_sms", new_callable=AsyncMock, return_value=True) as mock_sms:
        resp = await client.post(f"/v1/deals/{deal_id}/request-sign", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "SMS-код отправлен"
    mock_sms.assert_called_once()


@pytest.mark.asyncio
async def test_sign_wrong_code(client, advertiser_user, creator_user, chat, order):
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)

    with patch("app.routers.deals.send_sms", new_callable=AsyncMock, return_value=True):
        await client.post(f"/v1/deals/{deal_id}/request-sign", headers=auth_headers(advertiser_user))

    resp = await client.post(
        f"/v1/deals/{deal_id}/sign",
        json={"code": "000000"},
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 400
    assert "Неверный" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_sign_both_parties(client, advertiser_user, creator_user, chat, order, db):
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)

    # Advertiser signs
    with patch("app.routers.deals.send_sms", new_callable=AsyncMock, return_value=True):
        await client.post(f"/v1/deals/{deal_id}/request-sign", headers=auth_headers(advertiser_user))

    from sqlalchemy import select
    from app.models.deal import DealSignature
    result = await db.execute(
        select(DealSignature).where(DealSignature.deal_id == deal_id, DealSignature.user_id == advertiser_user.id)
    )
    sig = result.scalar_one()

    resp = await client.post(
        f"/v1/deals/{deal_id}/sign",
        json={"code": sig.sms_code},
        headers=auth_headers(advertiser_user),
    )
    assert resp.json()["deal_status"] == "contract_signed"

    # Creator signs
    with patch("app.routers.deals.send_sms", new_callable=AsyncMock, return_value=True):
        await client.post(f"/v1/deals/{deal_id}/request-sign", headers=auth_headers(creator_user))

    result = await db.execute(
        select(DealSignature).where(DealSignature.deal_id == deal_id, DealSignature.user_id == creator_user.id)
    )
    sig2 = result.scalar_one()

    resp = await client.post(
        f"/v1/deals/{deal_id}/sign",
        json={"code": sig2.sms_code},
        headers=auth_headers(creator_user),
    )
    assert resp.json()["deal_status"] == "pending_payment"


# ────────────────────────────────────────
# PAYMENT
# ────────────────────────────────────────

async def _sign_deal(client, deal_id, advertiser_user, creator_user, db):
    """Helper: both parties sign the deal."""
    from sqlalchemy import select
    from app.models.deal import DealSignature

    for user in [advertiser_user, creator_user]:
        with patch("app.routers.deals.send_sms", new_callable=AsyncMock, return_value=True):
            await client.post(f"/v1/deals/{deal_id}/request-sign", headers=auth_headers(user))
        result = await db.execute(
            select(DealSignature).where(DealSignature.deal_id == deal_id, DealSignature.user_id == user.id)
        )
        sig = result.scalar_one()
        await client.post(
            f"/v1/deals/{deal_id}/sign",
            json={"code": sig.sms_code},
            headers=auth_headers(user),
        )


@pytest.mark.asyncio
async def test_pay_deal(client, advertiser_user, creator_user, chat, order, db):
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)
    await _sign_deal(client, deal_id, advertiser_user, creator_user, db)

    resp = await client.post(
        f"/v1/deals/{deal_id}/pay",
        json={"payment_method": "kaspi"},
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["escrow_amount"] == 100000
    assert data["payment"]["method"] == "kaspi"


@pytest.mark.asyncio
async def test_pay_deal_wrong_status(client, advertiser_user, creator_user, chat, order):
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)

    resp = await client.post(
        f"/v1/deals/{deal_id}/pay",
        json={"payment_method": "kaspi"},
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 400


# ────────────────────────────────────────
# WORK SUBMISSION
# ────────────────────────────────────────

async def _deal_to_in_progress(client, advertiser_user, creator_user, chat, order, db):
    """Helper: create deal, sign, pay → in_progress."""
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)
    await _sign_deal(client, deal_id, advertiser_user, creator_user, db)
    await client.post(
        f"/v1/deals/{deal_id}/pay",
        json={"payment_method": "kaspi"},
        headers=auth_headers(advertiser_user),
    )
    return deal_id


@pytest.mark.asyncio
async def test_submit_work(client, advertiser_user, creator_user, chat, order, db):
    deal_id = await _deal_to_in_progress(client, advertiser_user, creator_user, chat, order, db)

    resp = await client.post(f"/v1/deals/{deal_id}/submit-work", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "work_submitted"
    assert data["work_submitted_at"] is not None


@pytest.mark.asyncio
async def test_submit_work_wrong_status(client, advertiser_user, creator_user, chat, order):
    deal_id = await _create_deal(client, advertiser_user, creator_user, chat, order)

    resp = await client.post(f"/v1/deals/{deal_id}/submit-work", headers=auth_headers(creator_user))
    assert resp.status_code == 400


# ────────────────────────────────────────
# CONFIRM WORK
# ────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_work(client, advertiser_user, creator_user, chat, order, db):
    deal_id = await _deal_to_in_progress(client, advertiser_user, creator_user, chat, order, db)
    await client.post(f"/v1/deals/{deal_id}/submit-work", headers=auth_headers(creator_user))

    resp = await client.post(f"/v1/deals/{deal_id}/confirm-work", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["payout"]["budget"] == 100000
    assert data["payout"]["platform_fee"] == 10000  # 10%
    assert data["payout"]["creator_payout"] == 90000


# ────────────────────────────────────────
# DISPUTE
# ────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispute(client, advertiser_user, creator_user, chat, order, db):
    deal_id = await _deal_to_in_progress(client, advertiser_user, creator_user, chat, order, db)
    await client.post(f"/v1/deals/{deal_id}/submit-work", headers=auth_headers(creator_user))

    resp = await client.post(
        f"/v1/deals/{deal_id}/dispute",
        json={"reason": "Видео не соответствует ТЗ"},
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "disputed"
    assert data["reason"] == "Видео не соответствует ТЗ"


@pytest.mark.asyncio
async def test_dispute_wrong_status(client, advertiser_user, creator_user, chat, order, db):
    deal_id = await _deal_to_in_progress(client, advertiser_user, creator_user, chat, order, db)

    resp = await client.post(
        f"/v1/deals/{deal_id}/dispute",
        json={"reason": "test"},
        headers=auth_headers(advertiser_user),
    )
    assert resp.status_code == 400


# ────────────────────────────────────────
# FULL HAPPY PATH
# ────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_deal_flow(client, advertiser_user, creator_user, chat, order, db):
    """Test the complete happy path: offer → accept → sign → pay → work → confirm."""
    # 1. Send offer
    offer_resp = await client.post(
        f"/v1/chats/{chat.id}/offer",
        json={
            "order_id": str(order.id),
            "budget": 200000,
            "deadline": "2026-05-01T00:00:00Z",
            "conditions": "3 видео",
            "video_count": 3,
        },
        headers=auth_headers(advertiser_user),
    )
    assert offer_resp.status_code == 201
    offer_id = offer_resp.json()["offer"]["id"]

    # 2. Accept offer
    accept_resp = await client.post(
        f"/v1/chats/{chat.id}/offer/{offer_id}/respond",
        json={"action": "accept"},
        headers=auth_headers(creator_user),
    )
    deal_id = accept_resp.json()["deal_id"]
    assert deal_id is not None

    # 3. Sign contract (both)
    await _sign_deal(client, deal_id, advertiser_user, creator_user, db)

    # Verify status
    deal_resp = await client.get(f"/v1/deals/{deal_id}", headers=auth_headers(advertiser_user))
    assert deal_resp.json()["status"] == "pending_payment"

    # 4. Pay
    pay_resp = await client.post(
        f"/v1/deals/{deal_id}/pay",
        json={"payment_method": "kaspi"},
        headers=auth_headers(advertiser_user),
    )
    assert pay_resp.json()["status"] == "in_progress"

    # 5. Submit work
    work_resp = await client.post(f"/v1/deals/{deal_id}/submit-work", headers=auth_headers(creator_user))
    assert work_resp.json()["status"] == "work_submitted"

    # 6. Confirm work
    confirm_resp = await client.post(f"/v1/deals/{deal_id}/confirm-work", headers=auth_headers(advertiser_user))
    assert confirm_resp.json()["status"] == "completed"
    assert confirm_resp.json()["payout"]["platform_fee"] == 20000  # 10% of 200000
    assert confirm_resp.json()["payout"]["creator_payout"] == 180000
