"""Exercise upstream ASGI browser protections used by the patched Streamlit server."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from streamlit import config
from streamlit.runtime.memory_uploaded_file_manager import MemoryUploadedFileManager
from streamlit.web.server.starlette.starlette_app import create_streamlit_middleware
from streamlit.web.server.starlette.starlette_routes import XSRF_COOKIE_NAME, create_health_routes, create_upload_routes
from streamlit.web.server.starlette.starlette_websocket import create_websocket_routes


class ReadyRuntime(SimpleNamespace):
    @property
    def is_ready_for_browser_connection(self):
        async def ready():
            return True, "ok"

        return ready()


@pytest.fixture
def server():
    runtime = ReadyRuntime(is_active_session=lambda value: value == "review-session", connect_session=Mock())
    manager = MemoryUploadedFileManager("/_stcore/upload_file")
    routes = create_health_routes(runtime, None) + create_upload_routes(runtime, manager, None) + create_websocket_routes(runtime, None)
    with TestClient(Starlette(routes=routes, middleware=create_streamlit_middleware())) as client:
        yield client, runtime, manager


def test_health_retains_xsrf_cookie_and_restricts_cross_origin_headers(server):
    client, _, _ = server
    assert config.get_option("server.enableCORS") is True
    assert config.get_option("server.enableXsrfProtection") is True
    assert config.get_option("server.enableStaticServing") is False
    response = client.get("/_stcore/health", headers={"Origin": "https://untrusted.invalid"})
    assert response.status_code == 200
    assert client.cookies.get(XSRF_COOKIE_NAME)
    assert "access-control-allow-origin" not in response.headers
    assert "samesite=lax" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_upload_requires_matching_xsrf_cookie_and_header(server, token):
    client, _, manager = server
    client.get("/_stcore/health")
    headers = {} if token is None else {"X-Xsrftoken": token}
    response = client.put(
        "/_stcore/upload_file/review-session/review-file",
        files={"file": ("synthetic.txt", b"synthetic", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 403
    assert not manager.get_files("review-session", ["review-file"])


def test_cross_origin_websocket_is_rejected_before_allocating_a_session(server):
    client, runtime, _ = server
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect("/_stcore/stream", headers={"Origin": "https://untrusted.invalid"}):
            pytest.fail("Cross-origin browser connection was accepted")
    assert caught.value.code == 1008
    runtime.connect_session.assert_not_called()
