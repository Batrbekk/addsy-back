"""Tests for profile endpoints."""
import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import auth_headers

SMS_PATCH = "app.services.sms.send_otp_sms"


@pytest.mark.asyncio
async def test_get_profile(client, creator_user):
    resp = await client.get("/v1/profile", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["phone"] == creator_user.phone
    assert data["role"] == "creator"


@pytest.mark.asyncio
async def test_get_profile_unauthorized(client):
    resp = await client.get("/v1/profile")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_choose_role(client, db):
    with patch(SMS_PATCH, new_callable=AsyncMock, return_value=True):
        await client.post("/v1/auth/send-otp", json={"phone": "+77051119999"})

    from sqlalchemy import select
    from app.models.otp import OTPCode
    result = await db.execute(select(OTPCode).where(OTPCode.phone == "+77051119999"))
    otp = result.scalar_one()

    verify_resp = await client.post("/v1/auth/verify-otp", json={"phone": "+77051119999", "code": otp.code})
    token = verify_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Choose role
    resp = await client.post("/v1/profile", json={"role": "creator"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "creator"
