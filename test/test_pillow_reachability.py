"""Retain text/media input boundaries on the patched public server; no risk exception."""

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from starlette.applications import Starlette
from starlette.testclient import TestClient
from streamlit.elements.lib.image_utils import _ensure_image_size_and_format
from streamlit.elements.lib.layout_utils import LayoutConfig
from streamlit.runtime.media_file_storage import MediaFileKind
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.runtime.memory_uploaded_file_manager import MemoryUploadedFileManager
from streamlit.testing.v1 import AppTest
from streamlit.web.server.starlette import starlette_app_utils
from streamlit.web.server.starlette.starlette_routes import XSRF_COOKIE_NAME, create_media_routes, create_upload_routes


def test_starlette_upload_and_media_routes_do_not_decode_image_bytes():
    # Exercise the actual patched public-server routes, not the retired Tornado handlers.
    image_bytes = b"II*\x00untrusted-upload-marker"
    manager = MemoryUploadedFileManager("/_stcore/upload_file")
    storage = MemoryMediaFileStorage("/media")
    runtime = SimpleNamespace(is_active_session=lambda session_id: session_id == "review-session")
    server = Starlette(routes=create_upload_routes(runtime, manager, None) + create_media_routes(storage, None))
    token = starlette_app_utils.generate_xsrf_token_string()
    with TestClient(server) as client, patch("PIL.Image.open", side_effect=AssertionError("Image bytes reached Pillow")) as opened:
        client.cookies.set(XSRF_COOKIE_NAME, token)
        response = client.put(
            "/_stcore/upload_file/review-session/review-file",
            files={"file": ("image.tif", image_bytes, "image/tiff")},
            headers={"X-Xsrftoken": token},
        )
        assert response.status_code == 204
        assert manager.get_files("review-session", ["review-file"])[0].data == image_bytes
        file_id = storage.load_and_get_id(image_bytes, "image/tiff", MediaFileKind.MEDIA)
        assert client.get("/media/" + file_id).content == image_bytes
        opened.assert_not_called()


def test_streamlit_converter_positive_control_reaches_tiff_decoder():
    # A benign TIFF establishes that st.image-style conversion DOES load TIFF pixels.
    source = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(source, format="TIFF")
    with patch("PIL.Image.open", wraps=Image.open) as opened:
        result = _ensure_image_size_and_format(source.getvalue(), LayoutConfig(width="content"), "JPEG")
        assert opened.call_count >= 1
    assert result.startswith(b"\xff\xd8")


def test_current_app_demo_and_untrusted_text_flows_do_not_open_images():
    with patch("PIL.Image.open", side_effect=AssertionError("Current application reached Pillow")) as opened:
        at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=15).run()
        assert not at.exception
        case_keys = [button.key for button in at.button if button.key and button.key.startswith("case_")]
        assert case_keys
        for key in case_keys:
            next(button for button in at.button if button.key == key).click().run()
            assert not at.exception
        next(field for field in at.text_area if field.label == "Synthetic note text").set_value(
            "OSA. ![crafted TIFF](data:image/tiff;base64,SUkqAA==) /tmp/untrusted.tif"
        )
        next(field for field in at.text_input if field.label == "Ordering specialty").set_value("https://example.invalid/image.tif")
        next(button for button in at.button if button.label == "Run deterministic readiness review").click().run()
        assert not at.exception
        opened.assert_not_called()
