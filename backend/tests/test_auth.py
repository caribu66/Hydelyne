"""Security regression tests: auth + login cookie."""
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_login_returns_token_and_cookie(client, monkeypatch):
    """Login mutation should return the bearer token AND set an HttpOnly cookie."""
    monkeypatch.setattr(
        "app.services.crew.auth_service.authenticate",
        AsyncMock(return_value={
            "token": "test_session_token",
            "user": {"id": "test-id", "full_name": "Test", "email": "test@example.com", "role": "admin"},
        }),
    )

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation Login($email: String!, $password: String!) {
                    login(email: $email, password: $password) {
                        success
                        token
                        user { id fullName email role }
                    }
                }
            """,
            "variables": {"email": "test@example.com", "password": "password"},
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["login"]
    assert data["success"] is True
    assert data["token"] == "test_session_token"
    assert data["user"]["role"] == "admin"
    # Cookie must be set with HttpOnly
    set_cookie = response.headers.get("set-cookie", "")
    assert "hydenlyne_session" in set_cookie
    assert "HttpOnly" in set_cookie


@pytest.mark.asyncio
async def test_unauthenticated_graphql_query_blocked(client, monkeypatch):
    """Without a valid token, GraphQL queries should return 401 UNAUTHENTICATED."""
    monkeypatch.setattr("app.auth.decorators._extract_token", lambda request: None)

    response = await client.post(
        "/graphql",
        json={"query": "{ crewMember(id: \"test\") { id fullName } }"},
    )
    assert response.status_code == 200  # GraphQL returns 200 even for errors
    body = response.json()
    assert "errors" in body
    assert "UNAUTHENTICATED" in str(body["errors"])


@pytest.mark.asyncio
async def test_login_failure_no_cookie(client, monkeypatch):
    """Failed login must not set a session cookie."""
    monkeypatch.setattr(
        "app.services.crew.auth_service.authenticate",
        AsyncMock(return_value=None),
    )

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation Login($email: String!, $password: String!) {
                    login(email: $email, password: $password) {
                        success
                        token
                    }
                }
            """,
            "variables": {"email": "nobody@example.com", "password": "wrong"},
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["login"]
    assert data["success"] is False
    set_cookie = response.headers.get("set-cookie", "")
    assert "hydenlyne_session" not in set_cookie


@pytest.mark.asyncio
async def test_rest_unauthenticated_access_blocked(client, monkeypatch):
    """REST endpoints must reject requests without auth."""
    monkeypatch.setattr("app.auth.decorators._extract_token", lambda request: None)

    response = await client.get("/api/documents/nonexistent-id/status")
    assert response.status_code == 401
