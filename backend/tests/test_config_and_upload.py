
from fastapi.testclient import TestClient

from app.core.dependencies import get_batch_service, get_settings
from app.core.settings import Settings
from app.main import app
from app.services.batch_service import BatchService
from helpers import (
    TestVerificationService,
)


def test_config_endpoint_exposes_safe_limits() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(provider_mode="local")
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_mode"] == "local"
    assert body["environment"] == "development"
    assert body["demo_batch_manifest_url"] is None
    assert body["tutorial_video_url"] is None
    assert body["max_batch_labels"] == 350
    assert ".png" in body["allowed_file_types"]
    assert ".pdf" not in body["allowed_file_types"]
    assert "openrouter_api_key" not in body


def test_config_endpoint_exposes_demo_manifest_only_in_production() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        provider_mode="local",
        environment="development",
        demo_batch_manifest_url="https://example.test/manifest.json",
        tutorial_video_url="https://example.test/tutorial.mp4",
    )
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "development"
    assert body["demo_batch_manifest_url"] is None
    assert body["tutorial_video_url"] is None

    app.dependency_overrides[get_settings] = lambda: Settings(
        provider_mode="local",
        environment="production",
        demo_batch_manifest_url="https://example.test/manifest.json",
        tutorial_video_url="https://example.test/tutorial.mp4",
    )

    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "production"
    assert body["demo_batch_manifest_url"] == "https://example.test/manifest.json"
    assert body["tutorial_video_url"] == "https://example.test/tutorial.mp4"


def test_settings_accept_comma_separated_cors_origins() -> None:
    settings = Settings(cors_origins="http://localhost:7001,http://127.0.0.1:7001")

    assert settings.cors_origin_list == [
        "http://localhost:7001",
        "http://127.0.0.1:7001",
    ]


def test_verify_rejects_invalid_upload() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"file": ("not-supported.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PNG, JPG, or JPEG files can be uploaded."


def test_batch_rejects_invalid_file_without_creating_batch() -> None:
    test_batch_service = BatchService(
        settings=Settings(provider_mode="local"),
        verification_service=TestVerificationService(),
    )

    app.dependency_overrides[get_batch_service] = lambda: test_batch_service
    client = TestClient(app)

    response = client.post(
        "/api/batches",
        files=[("files", ("not-supported.txt", b"hello", "text/plain"))],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PNG, JPG, or JPEG files can be uploaded."
    assert test_batch_service._batches == {}
