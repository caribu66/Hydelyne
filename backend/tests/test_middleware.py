import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware import SecurityHeadersMiddleware, _safe_request_path


def test_public_upload_link_token_is_not_logged() -> None:
    path = "/api/documents/request/sensitive-bearer-token/upload"

    assert _safe_request_path(path) == "/api/documents/request/[redacted-token]/upload"


def test_non_token_paths_remain_useful_for_diagnostics() -> None:
    path = "/api/documents/123/status"

    assert _safe_request_path(path) == path


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/graphql", "/api/search/crew"])
async def test_private_api_responses_are_not_cacheable(path: str) -> None:
    scope = {
        "type": "http",
        "path": path,
        "raw_path": path.encode(),
        "method": "POST" if path == "/graphql" else "GET",
        "scheme": "https",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 443),
        "client": ("127.0.0.1", 1234),
    }
    request = Request(scope)

    async def call_next(_: Request) -> Response:
        return Response("ok")

    async def app(*_args: object) -> None:
        return None

    middleware = SecurityHeadersMiddleware(app)
    response = await middleware.dispatch(request, call_next)

    assert response.headers["Cache-Control"] == "no-store"
