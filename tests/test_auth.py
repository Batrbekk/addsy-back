"""Tests for auth endpoints: send-otp, verify-otp, refresh."""
import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import auth_headers

SMS_PATCH = "app.services.sms.send_otp_sms"


@pytest.mark.asyncio
async def test_send_otp(client):
    with patch(SMS_PATCH, new_callable=AsyncMock, return_value=True):
        resp = await client.post("/v1/auth/send-otp", json={"phone": "+77051234567"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "OTP sent"


@pytest.mark.asyncio
async def test_send_otp_rate_limit(client):
    with patch(SMS_PATCH, new_callable=AsyncMock, return_value=True):
        await client.post("/v1/auth/send-otp", json={"phone": "+77051234567"})
        resp = await client.post("/v1/auth/send-otp", json={"phone": "+77051234567"})
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_verify_otp_wrong_code(client):
    with patch(SMS_PATCH, new_callable=AsyncMock, return_value=True):
        await client.post("/v1/auth/send-otp", json={"phone": "+77051234567"})
    resp = await client.post("/v1/auth/verify-otp", json={"phone": "+77051234567", "code": "000000"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_otp_success(client, db):
    with patch(SMS_PATCH, new_callable=AsyncMock, return_value=True):
        await client.post("/v1/auth/send-otp", json={"phone": "+77051234567"})

    # Get the OTP code from db
    from sqlalchemy import select
    from app.models.otp import OTPCode
    result = await db.execute(select(OTPCode).where(OTPCode.phone == "+77051234567"))
    otp = result.scalar_one()

    resp = await client.post("/v1/auth/verify-otp", json={"phone": "+77051234567", "code": otp.code})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "refresh_token" in data
    assert data["user"]["phone"] == "+77051234567"


@pytest.mark.asyncio
async def test_refresh_token(client, db):
    with patch(SMS_PATCH, new_callable=AsyncMock, return_value=True):
        await client.post("/v1/auth/send-otp", json={"phone": "+77051234567"})

    from sqlalchemy import select
    from app.models.otp import OTPCode
    result = await db.execute(select(OTPCode).where(OTPCode.phone == "+77051234567"))
    otp = result.scalar_one()

    verify_resp = await client.post("/v1/auth/verify-otp", json={"phone": "+77051234567", "code": otp.code})
    refresh_token = verify_resp.json()["refresh_token"]

    resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "token" in resp.json()
    assert "refresh_token" in resp.json()
