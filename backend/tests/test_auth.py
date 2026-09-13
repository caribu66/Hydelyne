"""Security regression tests: auth + login cookie."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_passwordless_development_login_requires_explicit_opt_in(monkeypatch):
    class SessionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            del statement
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [user]),
            )

    user = SimpleNamespace(
        id="user-1",
        full_name="Development User",
        email="dev@example.com",
        role="user",
        password_hash=None,
    )
    settings = SimpleNamespace(
        APP_ENV="development",
        ALLOW_PASSWORDLESS_DEV_LOGIN=False,
    )
    monkeypatch.setattr("app.services.crew.get_session_factory", lambda: lambda: SessionContext())
    monkeypatch.setattr("app.config.get_settings", lambda: settings)

    from app.services.crew import auth_service

    assert await auth_service.authenticate("dev@example.com", "anything") is None

    settings.ALLOW_PASSWORDLESS_DEV_LOGIN = True
    monkeypatch.setattr("app.services.crew.create_session_token", lambda user_id: "token")
    result = await auth_service.authenticate("dev@example.com", "anything")
    assert result is not None
    assert result["token"] == "token"


@pytest.mark.asyncio
async def test_unknown_login_email_still_verifies_dummy_password(monkeypatch):
    class SessionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            del statement
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: []),
            )

    monkeypatch.setattr(
        "app.services.crew.get_session_factory", lambda: lambda: SessionContext()
    )
    password_check = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.crew.verify_password", password_check)

    from app.services.crew import auth_service

    assert await auth_service.authenticate("missing@example.com", "password") is None
    password_check.assert_called_once()


def test_password_verifier_rejects_extreme_pbkdf2_cost() -> None:
    from app.auth.session import verify_password

    assert (
        verify_password(
            "password",
            "pbkdf2_sha256$999999999$ignored-salt$ignored-hash",
        )
        is False
    )


@pytest.mark.asyncio
async def test_login_returns_user_and_http_only_cookie_without_exposing_token(client, monkeypatch):
    """Login delivers the session only through the HttpOnly cookie."""
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
                        user { id fullName email role publicationStatus availabilityStatus }
                    }
                }
            """,
            "variables": {"email": "test@example.com", "password": "password"},
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["login"]
    assert data["success"] is True
    assert data["token"] is None
    assert data["user"]["role"] == "admin"
    assert data["user"]["publicationStatus"] == "draft"
    assert data["user"]["availabilityStatus"] == "unavailable"
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
async def test_login_rejects_oversized_credentials_before_authentication(client, monkeypatch):
    authenticate = AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.crew.auth_service.authenticate", authenticate)

    response = await client.post(
        "/graphql",
        json={
            "query": "mutation Login($email: String!, $password: String!) { login(email: $email, password: $password) { success } }",
            "variables": {"email": "x" * 321, "password": "secret"},
        },
    )

    assert response.json()["data"]["login"]["success"] is False
    authenticate.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_fails_closed_for_duplicate_login_emails(db_session):
    """Distinct profile rows must not make login select an arbitrary account."""
    from app.auth.session import hash_password
    from app.models import CrewMember
    from app.services.crew import auth_service

    db_session.add_all(
        [
            CrewMember(
                full_name="Duplicate Login One",
                email="Duplicate.Login@example.com",
                password_hash=hash_password("correct-password"),
            ),
            CrewMember(
                full_name="Duplicate Login Two",
                email=" duplicate.login@example.com ",
                password_hash=hash_password("correct-password"),
            ),
        ]
    )
    await db_session.commit()

    result = await auth_service.authenticate("  DUPLICATE.LOGIN@EXAMPLE.COM ", "correct-password")

    assert result is None


def test_session_payload_without_jti_is_rejected():
    """Every accepted session must have a revocable token identifier."""
    from app.auth.session import serializer, verify_session_token

    token = serializer.dumps({"user_id": "user-without-jti"})

    assert verify_session_token(token) is None


@pytest.mark.asyncio
async def test_logout_clears_legacy_session_cookie(client, monkeypatch):
    """Logout must clear every cookie name accepted by authentication."""
    import uuid

    from app.models import CrewMember

    user = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Legacy Cookie User",
        email="legacy-cookie@example.com",
        role="user",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr("app.auth.session.revoke_session_token", AsyncMock())

    response = await client.post(
        "/graphql",
        headers={"Cookie": "session=legacy-token"},
        json={"query": "mutation { logout }"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["logout"] is True
    set_cookies = response.headers.get_list("set-cookie")
    assert any(cookie.startswith("hydenlyne_session=") for cookie in set_cookies)
    assert any(cookie.startswith("session=") for cookie in set_cookies)


@pytest.mark.asyncio
async def test_logout_reports_failed_session_revocation(client, monkeypatch):
    """Logout must not claim server-side revocation succeeded when Redis failed."""
    import uuid

    from app.models import CrewMember

    user = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Revocation Failure User",
        email="revocation-failure@example.com",
        role="user",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(
        "app.auth.session.revoke_session_token",
        AsyncMock(return_value=False),
    )

    response = await client.post(
        "/graphql",
        headers={"Cookie": "session=legacy-token"},
        json={"query": "mutation { logout }"},
    )

    body = response.json()
    assert any(
        error.get("extensions", {}).get("code") == "SERVICE_UNAVAILABLE"
        for error in body.get("errors", [])
    )
    set_cookies = response.headers.get_list("set-cookie")
    assert any(cookie.startswith("hydenlyne_session=") for cookie in set_cookies)
    assert any(cookie.startswith("session=") for cookie in set_cookies)


@pytest.mark.asyncio
async def test_rest_unauthenticated_access_blocked(client, monkeypatch):
    """REST endpoints must reject requests without auth."""
    monkeypatch.setattr("app.auth.decorators._extract_token", lambda request: None)

    response = await client.get("/api/documents/nonexistent-id/status")
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "{ campaignAssignments { id roleOnBoard } }",
        '{ vesselRoster(imo: "1234567") { id roleOnBoard } }',
    ],
)
async def test_t1_cannot_read_operational_assignment_rosters(client, monkeypatch, query):
    """Assignment rosters are C2 operational data, not general T1 data."""
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
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        '{ vesselSearch(name: "Explorer") { configured } }',
        '{ vesselPosition(vesselId: "1234567", idType: IMO) { imo } }',
        "{ vesselsInRadius(latitude: 57.0, longitude: -2.0, radius: 1000) { configured } }",
        '{ vesselRecord(imo: "1234567") { imo } }',
    ],
)
async def test_t1_cannot_read_vessel_operations(client, monkeypatch, query):
    """Vessel operations are staff-only even when a client forges GraphQL."""
    import uuid as _uuid

    from app.models import CrewMember

    regular_user = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Regular Vessel User",
        email="vessel-user@test.com",
        role="user",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=regular_user),
    )

    response = await client.post("/graphql", json={"query": query})

    body = response.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


@pytest.mark.asyncio
async def test_staff_cannot_read_assignment_compliance_medical_details(client, monkeypatch):
    """Assignment compliance includes medical data and is T3/admin-only."""
    import uuid as _uuid

    from app.models import CrewMember

    staff_user = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Staff User",
        email="staff@test.com",
        role="staff",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=staff_user),
    )
    response = await client.post(
        "/graphql",
        json={
            "query": """
                query {
                    evaluateAssignmentCompliance(
                        crewMemberId: "crew-id"
                        startDate: "2026-10-01"
                        endDate: "2026-10-10"
                    ) { status }
                }
            """
        },
    )

    body = response.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


@pytest.mark.asyncio
async def test_staff_cannot_assign_another_staff_members_draft(client, db_session, monkeypatch):
    """Staff assignment writes must preserve draft ownership boundaries."""
    import uuid as _uuid

    from app.models import CrewMember

    other_owner_id = str(_uuid.uuid4())
    draft = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Private Draft",
        role="user",
        publication_status="draft",
        submitted_by=other_owner_id,
    )
    db_session.add(draft)
    await db_session.commit()
    staff_user = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Staff User",
        email="staff@test.com",
        role="staff",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=staff_user),
    )
    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($input: CreateCampaignAssignmentInput!) {
                    createCampaignAssignment(input: $input) { id }
                }
            """,
            "variables": {
                "input": {
                    "crewMemberId": draft.id,
                    "vesselImo": "1234567",
                    "roleOnBoard": "Operator",
                    "startDate": "2026-10-01",
                    "endDate": "2026-10-10",
                }
            },
        },
    )

    body = response.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


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
    assert any(
        e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"]
    ), f"{mutation_name} did not return FORBIDDEN for a non-admin caller: {body}"


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


@pytest.mark.asyncio
async def test_admin_metadata_only_upload_document_is_retired(client, monkeypatch):
    """The legacy GraphQL metadata-only path must not create a fake document row."""
    import uuid as _uuid

    from app.models import CrewMember

    admin = CrewMember(
        id=str(_uuid.uuid4()),
        full_name="Admin User",
        email="admin@test.com",
        role="admin",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=admin),
    )

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    uploadDocument(
                        crewId: "crew-id",
                        fileName: "x.pdf",
                        fileType: "application/pdf",
                        fileSize: 1
                    ) { id }
                }
            """
        },
    )
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"


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


@pytest.mark.asyncio
async def test_is_token_revoked_fails_closed_when_redis_unavailable(monkeypatch):
    """ADR 0002: Token revocation must fail closed when Redis is unavailable."""
    from app.auth.session import is_token_revoked
    from app.services.cache import cache_service

    monkeypatch.setattr(cache_service, "is_redis_available", AsyncMock(return_value=False))
    assert await is_token_revoked("test-jti-123") is True


@pytest.mark.asyncio
async def test_is_token_revoked_fails_closed_when_redis_raises_error(monkeypatch):
    """ADR 0002: Token revocation must fail closed when Redis get raises an exception."""
    from unittest.mock import MagicMock

    from app.auth.session import is_token_revoked
    from app.services.cache import cache_service

    monkeypatch.setattr(cache_service, "is_redis_available", AsyncMock(return_value=True))
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis connection dropped"))
    monkeypatch.setattr(cache_service, "_get_redis", AsyncMock(return_value=mock_redis))

    assert await is_token_revoked("test-jti-456") is True


@pytest.mark.asyncio
async def test_is_token_revoked_reflects_blocklist(monkeypatch):
    """Token revocation returns True when revoked, False when unrevoked."""
    from unittest.mock import MagicMock

    from app.auth.session import is_token_revoked
    from app.services.cache import cache_service

    monkeypatch.setattr(cache_service, "is_redis_available", AsyncMock(return_value=True))
    mock_redis = MagicMock()
    # First call: revoked; second call: unrevoked
    mock_redis.get = AsyncMock(side_effect=[b"revoked", None])
    monkeypatch.setattr(cache_service, "_get_redis", AsyncMock(return_value=mock_redis))

    assert await is_token_revoked("revoked-jti") is True
    assert await is_token_revoked("active-jti") is False
