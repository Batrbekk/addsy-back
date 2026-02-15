"""Tests for advertisers endpoints."""
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_list_advertisers(client, creator_user, advertiser_user):
    resp = await client.get("/v1/advertisers", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["company_name"] == "TestCorp"


@pytest.mark.asyncio
async def test_list_advertisers_filter_industry(client, creator_user, advertiser_user):
    resp = await client.get("/v1/advertisers?industry=fintech", headers=auth_headers(creator_user))
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/advertisers?industry=retail", headers=auth_headers(creator_user))
    assert len(resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_get_advertiser_detail(client, creator_user, advertiser_user):
    resp = await client.get(f"/v1/advertisers/{advertiser_user.id}", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "TestCorp"
    assert "review_breakdown" in data
