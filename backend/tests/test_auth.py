"""Security regression tests: auth + login cookie."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_login_returns_token_and_cookie(client, monkeypatch):
    """Login mutation should return the bearer token AND set an HttpOnly cookie."""
    monkeypatch.setattr(
        "app.services.crew.auth_service.authenticate",
        AsyncMock(
            return_value={
                "token": "test_session_token",
                "user": {
                    "id": "test-id",
                    "full_name": "Test",
                    "email": "test@example.com",
                    "role": "admin",
                },
            }
        ),
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
        json={"query": '{ crewMember(id: "test") { id fullName } }'},
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


@pytest.mark.asyncio
async def test_non_admin_blocked_from_create_crew_member(client, monkeypatch):
    """Non-admin users must be FORBIDDEN from createCrewMember."""
    import uuid as _uuid

    from app.models import CrewMember

    regular_user = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Regular User",
        email="user@test.com",
        role="user",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=regular_user),
    )

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation Create($fullName: String!) {
                    createCrewMember(fullName: $fullName) { id fullName }
                }
            """,
            "variables": {"fullName": "Should Be Blocked"},
        },
    )
    body = response.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


# Every remaining admin-gated mutation from docs/AUTHORIZATION.md, minus the
# two already covered above by their own named tests. createCrewMember and
# uploadDocument had negative-auth coverage; the other twelve did not, which
# is exactly the "add negative authorization tests for every mutation" gap
# docs/AUDIT_2026-09-02.md (P1 #4) called out.
_OTHER_ADMIN_MUTATIONS = [
    ("updateCrewMember", 'mutation { updateCrewMember(id: "x") { id } }'),
    ("deleteCrewMember", 'mutation { deleteCrewMember(id: "x") }'),
    ("confirmExtraction", 'mutation { confirmExtraction(documentId: "x", data: "{}") { id } }'),
    ("reprocessDocument", 'mutation { reprocessDocument(documentId: "x") { id } }'),
    (
        "confirmDocumentMatch",
        'mutation { confirmDocumentMatch(documentId: "x", crewId: "x") { id } }',
    ),
    ("addCertification", 'mutation { addCertification(crewId: "x", certType: BOSIET) { id } }'),
    ("updateCertification", 'mutation { updateCertification(id: "x") { id } }'),
    ("verifyCertification", 'mutation { verifyCertification(id: "x", status: VERIFIED) { id } }'),
    (
        "createProject",
        'mutation { createProject(clientName: "x", projectName: "x", projectType: OTHER) { id } }',
    ),
    ("updateProject", 'mutation { updateProject(id: "x") { id } }'),
    (
        "assignCrewToProject",
        'mutation { assignCrewToProject(projectId: "x", crewIds: ["x"]) { id } }',
    ),
    (
        "uploadCvAndExtract",
        'mutation { uploadCvAndExtract(crewId: "x", fileName: "x.pdf", '
        'fileType: "application/pdf", fileSize: 1) { documentId } }',
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation_name,query", _OTHER_ADMIN_MUTATIONS)
async def test_non_admin_blocked_from_admin_mutation(client, monkeypatch, mutation_name, query):
    """Non-admin users must be FORBIDDEN from every admin-only mutation."""
    import uuid as _uuid

    from app.models import CrewMember

    regular_user = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Regular User",
        email="user@test.com",
        role="user",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=regular_user),
    )

    response = await client.post("/graphql", json={"query": query})
    body = response.json()
    assert "errors" in body, f"{mutation_name} did not error for a non-admin caller: {body}"
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"]), (
        f"{mutation_name} did not return FORBIDDEN for a non-admin caller: {body}"
    )


@pytest.mark.asyncio
async def test_non_admin_blocked_from_upload_document_mutation(client, monkeypatch):
    """Non-admin users must be FORBIDDEN from uploadDocument."""
    import uuid as _uuid

    from app.models import CrewMember

    regular_user = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Regular User",
        email="user@test.com",
        role="user",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=regular_user),
    )

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation Upload($crewId: String!, $fileName: String!, $fileType: String!, $fileSize: Int!) {
                    uploadDocument(crewId: $crewId, fileName: $fileName, fileType: $fileType, fileSize: $fileSize) { id }
                }
            """,
            "variables": {
                "crewId": "x",
                "fileName": "x.pdf",
                "fileType": "application/pdf",
                "fileSize": 1,
            },
        },
    )
    body = response.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


# docs/AUTHORIZATION.md claims "All queries remain @require_auth" but, unlike
# the admin-mutation table above, had no test proving it — only the doc's
# prose. Fields added here without the decorator are caught by default: they
# must be deliberately (and visibly) added below with a reason, mirroring the
# admin-mutation list's "add a case when you add a mutation" policy for
# queries specifically.
_PUBLIC_QUERIES: set[str] = set()


def test_all_queries_require_auth_decorator():
    """Every Query field must be wrapped by @require_auth or @require_admin.

    Checks the resolver's underlying code object rather than calling each
    field, so it's independent of DB/service mocking and decorator-agnostic
    (catches require_auth and require_admin alike) — a missing decorator
    fails this test immediately instead of shipping an unauthenticated read.
    """
    from app.graphql.schema import Query

    fields = Query.__strawberry_definition__.fields
    assert fields, "Query type has no fields — introspection broke, not that auth is fine"

    for field in fields:
        if field.name in _PUBLIC_QUERIES:
            continue
        assert field.base_resolver is not None, f"Query.{field.name} has no resolver"
        code = field.base_resolver.wrapped_func.__code__
        assert code.co_filename.endswith("app/auth/decorators.py") and code.co_name == "wrapper", (
            f"Query.{field.name} is not wrapped by @require_auth/@require_admin — "
            f"add the decorator, or add '{field.name}' to _PUBLIC_QUERIES above with a reason."
        )
