"""Security-focused tests for file upload validation and input sanitization."""

import io

import pytest

from dpa_app.services.analysis_service import validate_upload, save_upload
from dpa_app.config import settings


class TestFileValidation:
    def _make_upload(self, filename: str, content_type: str = "application/octet-stream"):
        """Create a mock UploadFile-like object."""
        from starlette.datastructures import UploadFile as StarletteUpload
        file = io.BytesIO(b"test content")
        return StarletteUpload(file=file, filename=filename, headers={"content-type": content_type})

    def test_reject_txt_file(self):
        upload = self._make_upload("evil.txt")
        with pytest.raises(Exception, match="Unsupported file type"):
            validate_upload(upload)

    def test_reject_exe_file(self):
        upload = self._make_upload("malware.exe")
        with pytest.raises(Exception, match="Unsupported file type"):
            validate_upload(upload)

    def test_reject_no_filename(self):
        from starlette.datastructures import UploadFile as StarletteUpload
        file = io.BytesIO(b"test")
        upload = StarletteUpload(file=file, filename="")
        with pytest.raises(Exception, match="Filename"):

            validate_upload(upload)

    def test_accept_docx(self):
        upload = self._make_upload("contract.docx")
        validate_upload(upload)  # Should not raise

    def test_accept_pdf(self):
        upload = self._make_upload("agreement.pdf", "application/pdf")
        validate_upload(upload)  # Should not raise

    def test_reject_double_extension(self):
        upload = self._make_upload("evil.pdf.exe")
        with pytest.raises(Exception, match="Unsupported file type"):
            validate_upload(upload)


class TestFileSave:
    def test_uuid_filename(self, tmp_path, monkeypatch):
        from dpa_app import config
        monkeypatch.setattr(config.settings, "uploads_dir", tmp_path)

        from starlette.datastructures import UploadFile as StarletteUpload
        content = b"test pdf content"
        file = StarletteUpload(
            file=io.BytesIO(content),
            filename="sensitive_name.pdf",
            headers={"content-type": "application/pdf"},
        )

        file_id, file_path, size = save_upload(file)

        # File ID is a UUID, not the original filename
        assert "sensitive_name" not in str(file_path)
        assert file_id in str(file_path)
        assert file_path.suffix == ".pdf"
        assert size == len(content)
        assert file_path.exists()

    def test_file_size_limit(self, tmp_path, monkeypatch):
        from dpa_app import config
        monkeypatch.setattr(config.settings, "uploads_dir", tmp_path)
        monkeypatch.setattr(config.settings, "max_file_size_mb", 0)  # 0 MB = reject everything

        from starlette.datastructures import UploadFile as StarletteUpload
        file = StarletteUpload(
            file=io.BytesIO(b"some content"),
            filename="big.pdf",
            headers={"content-type": "application/pdf"},
        )

        with pytest.raises(Exception, match="too large"):
            save_upload(file)
