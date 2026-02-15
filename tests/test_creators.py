"""Tests for creators endpoints."""
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_list_creators(client, creator_user, advertiser_user):
    resp = await client.get("/v1/creators", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "Test Creator"
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_creators_filter_category(client, creator_user, advertiser_user):
    resp = await client.get("/v1/creators?category=lifestyle", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/creators?category=gaming", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_list_creators_search_q(client, creator_user, advertiser_user):
    resp = await client.get("/v1/creators?q=Test", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    resp = await client.get("/v1/creators?q=Nonexistent", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_get_creator_detail(client, creator_user, advertiser_user):
    resp = await client.get(f"/v1/creators/{creator_user.id}", headers=auth_headers(advertiser_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Creator"
    assert "review_breakdown" in data


@pytest.mark.asyncio
async def test_get_creator_not_found(client, advertiser_user):
    resp = await client.get("/v1/creators/00000000-0000-0000-0000-000000000000", headers=auth_headers(advertiser_user))
    assert resp.status_code == 404
