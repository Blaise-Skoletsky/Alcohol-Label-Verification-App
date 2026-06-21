
from fastapi.testclient import TestClient

from app.core.dependencies import get_verification_service
from app.main import app
from app.models.application import ApplicationValues
from app.services.result_guard_service import (
    GOVERNMENT_WARNING_FULL_TEXT,
)
from app.services.verification_service import VerificationService
from helpers import (
    ErrorVerificationService,
    PNG_BYTES,
    TestVerificationService,
    WireFakeProvider,
    make_chat_completion_result_content,
    make_raw_warning_field,
    make_test_client,
    sample_label_path,
)


def test_verify_uses_verification_service() -> None:
    client = make_test_client()

    response = client.post(
        "/api/verify",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["model"]["provider"] == "test"
    assert body["model"]["model"] == "test-double"
    assert body["fields"]["brand_name"]["status"] == "pass"
    assert body["fields"]["brand_name"]["application_value"] == "Example Brand"
    assert body["fields"]["brand_name"]["label_value"] == "Example Brand"


def test_single_verify_returns_http_error_when_processing_fails() -> None:
    error_service = ErrorVerificationService()

    def override_verification_service() -> ErrorVerificationService:
        return error_service

    app.dependency_overrides[get_verification_service] = override_verification_service
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "The model returned an unreadable response."


def test_single_verify_guard_fails_cleo_lowercase_warning_from_wire_response() -> None:
    content = make_chat_completion_result_content(
        government_warning=make_raw_warning_field(
            status="pass",
            label_value=GOVERNMENT_WARNING_FULL_TEXT,
            reason="Model incorrectly canonicalized the visible lowercase heading.",
            warning_heading_text="government warning:",
            warning_full_text=GOVERNMENT_WARNING_FULL_TEXT.replace(
                "GOVERNMENT WARNING:", "government warning:"
            ),
        )
    )
    verification_service = VerificationService(WireFakeProvider(content))
    app.dependency_overrides[get_verification_service] = lambda: verification_service
    client = TestClient(app)
    cleo_path = sample_label_path("fail/cleo_2019-04-17_lowercase_warning.png")

    with open(cleo_path, "rb") as file:
        response = client.post(
            "/api/verify",
            files={"file": ("cleo_2019-04-17_lowercase_warning.png", file, "image/png")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fail"
    assert body["fields"]["government_warning"]["status"] == "fail"
    assert "government warning:" in body["fields"]["government_warning"]["label_value"]
    assert "GOVERNMENT WARNING:" not in body["fields"]["government_warning"]["label_value"]
    assert "warning_heading_text" not in body["fields"]["government_warning"]
    assert "heading words 'GOVERNMENT WARNING' are visible in all caps" in (
        body["fields"]["government_warning"]["reason"]
    )


def test_verify_forwards_application_values_to_service() -> None:
    service = TestVerificationService()
    app.dependency_overrides[get_verification_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
        data={
            "brand_name": "Coyam",
            "beverage_class": "wine",
            "class_type_designation": "Red Wine",
            "alcohol_content": "14.5%",
            "net_contents": "750 mL",
            "name_address": "Banfi Products Corp",
            "country_of_origin": "Chile",
            "malt_added_nonbeverage_alcohol": "false",
            "malt_color_additive_applicable": "false",
        },
    )

    assert response.status_code == 200
    values = service.last_application_values
    assert isinstance(values, ApplicationValues)
    assert values.brand_name == "Coyam"
    assert values.beverage_class == "wine"
    assert values.net_contents == "750 mL"
    assert values.country_of_origin == "Chile"
    assert values.malt_added_nonbeverage_alcohol is False
    assert values.malt_color_additive_applicable is False
