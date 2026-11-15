"""Test general API endpoints, health check, and OpenAPI documentation."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_openapi_docs(async_client: AsyncClient) -> None:
    """Verifies service health check and OpenAPI documentation availability."""
    # 1. Health check
    res_health = await async_client.get("/health")
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["status"] == "healthy"
    assert data["service"] == "agent-social-network"

    # 2. OpenAPI schema JSON
    res_openapi = await async_client.get("/openapi.json")
    assert res_openapi.status_code == 200
    openapi_spec = res_openapi.json()
    assert "paths" in openapi_spec
    assert "/api/v1/posts" in openapi_spec["paths"]
    assert "/api/v1/agents/register" in openapi_spec["paths"]

    # 3. Interactive Docs
    res_docs = await async_client.get("/docs")
    assert res_docs.status_code == 200
