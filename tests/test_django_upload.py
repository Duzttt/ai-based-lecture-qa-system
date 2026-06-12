import os
from pathlib import Path

import django
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from app.config import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_upload_pdf_success(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(settings, "DOCUMENTS_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "UPLOAD_INDEXING_STRATEGY", "full_rebuild")
    monkeypatch.setattr(settings, "UPLOAD_INDEXING_ASYNC", True)
    monkeypatch.setattr(
        "django_app.views.documents._enqueue_full_rebuild",
        lambda uploaded_filename: {
            "status": "queued",
            "last_uploaded_filename": uploaded_filename,
        },
    )

    file = SimpleUploadedFile(
        "lecture.pdf",
        b"%PDF-1.4 dummy content",
        content_type="application/pdf",
    )

    response = client.post("/api/upload", {"file": file})

    assert response.status_code == 202
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "File uploaded. Full reindex is running in background."
    assert data["indexing_mode"] == "full_rebuild"
    assert data["indexing_status"] == "queued"
    assert data["filename"].endswith("lecture.pdf")

    saved_file = tmp_path / data["filename"]
    assert saved_file.exists()


def test_upload_index_status_endpoint(client: Client):
    response = client.get("/api/upload/status")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_upload_pdf_rejects_invalid_extension(client: Client):
    file = SimpleUploadedFile(
        "lecture.txt",
        b"not a pdf",
        content_type="text/plain",
    )

    response = client.post("/api/upload", {"file": file})

    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_upload_pdf_rejects_large_file(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 10)

    file = SimpleUploadedFile(
        "lecture.pdf",
        b"0123456789ABCDEF",
        content_type="application/pdf",
    )

    response = client.post("/api/upload", {"file": file})

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]
