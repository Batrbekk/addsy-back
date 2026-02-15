"""Tests for tags endpoint."""
import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_list_tags(client, creator_user, advertiser_user, order):
    resp = await client.get("/v1/tags", headers=auth_headers(creator_user))
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "industries" in data
    assert "platforms" in data
    assert "cities" in data
    assert "lifestyle" in data["categories"]
    assert "instagram" in data["platforms"]


@pytest.mark.asyncio
async def test_tags_includes_creator_categories(client, creator_user, advertiser_user):
    resp = await client.get("/v1/tags", headers=auth_headers(creator_user))
    data = resp.json()
    # Creator has ["lifestyle", "tech"]
    assert "tech" in data["categories"]
