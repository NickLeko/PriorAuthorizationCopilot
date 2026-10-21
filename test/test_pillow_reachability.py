"""Evidence for the temporary exception; these checks are not an exploitability proof."""

import io
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image
from streamlit.elements.lib.image_utils import _ensure_image_size_and_format
from streamlit.elements.lib.layout_utils import LayoutConfig
from streamlit.runtime.media_file_storage import MediaFileKind
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.runtime.memory_uploaded_file_manager import MemoryUploadedFileManager
from streamlit.testing.v1 import AppTest
from streamlit.web.server.media_file_handler import MediaFileHandler
from streamlit.web.server.upload_file_request_handler import UploadFileRequestHandler


def test_tornado_upload_and_media_handlers_do_not_decode_image_bytes():
    # Deliberately incomplete TIFF header: it must be stored verbatim, never opened.
    image_bytes = b"II*\x00untrusted-upload-marker"
    body = (
        b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="image.tif"\r\n'
        b"Content-Type: image/tiff\r\n\r\n" + image_bytes + b"\r\n--boundary--\r\n"
    )
    manager = MemoryUploadedFileManager("/_stcore/upload_file")
    handler = SimpleNamespace(
        path_kwargs={"session_id": "review-session", "file_id": "review-file"},
        request=SimpleNamespace(headers={"Content-Type": "multipart/form-data; boundary=boundary"}, body=body),
        _file_mgr=manager,
        _is_active_session=lambda session_id: session_id == "review-session",
        send_error=Mock(side_effect=AssertionError("Upload unexpectedly rejected")),
        set_status=Mock(),
    )
    storage = MemoryMediaFileStorage("/media")
    with patch("PIL.Image.open", side_effect=AssertionError("Image bytes reached Pillow")) as opened:
        UploadFileRequestHandler.put(handler)
        handler.set_status.assert_called_once_with(204)
        assert manager.get_files("review-session", ["review-file"])[0].data == image_bytes
        file_id = storage.load_and_get_id(image_bytes, "image/tiff", MediaFileKind.MEDIA)
        with patch.object(MediaFileHandler, "_storage", storage, create=True):
            assert MediaFileHandler.get_content(file_id) == image_bytes
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
        at = AppTest.from_file("app.py", default_timeout=15).run()
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
