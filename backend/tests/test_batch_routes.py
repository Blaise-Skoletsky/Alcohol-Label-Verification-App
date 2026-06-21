import json
import logging
import time

from fastapi.testclient import TestClient

from app.core.dependencies import get_batch_service
from app.core.settings import Settings
from app.main import app
from app.models.application import ApplicationValues
from app.models.uploads import ValidatedUpload
from app.models.verification import (
    ModelMetadata,
    VerificationStatus,
)
from app.providers.base import ProviderResult
from app.providers.chat_completion_parser import (
    parse_chat_completion_response,
)
from app.services.batch_service import BatchService
from app.services.result_guard_service import (
    GOVERNMENT_WARNING_FULL_TEXT,
)
from app.services.verification_service import VerificationService
from helpers import (
    PNG_BYTES,
    WireFakeProvider,
    make_chat_completion_result_content,
    make_fields,
    make_provider_response,
    make_raw_warning_field,
    make_test_client,
    sample_label_path,
    wait_for_batch,
)


def test_batch_submission_and_progress_shape() -> None:
    client = make_test_client()

    response = client.post(
        "/api/batches",
        files=[
            ("files", ("sample-one.png", PNG_BYTES, "image/png")),
            ("files", ("sample-two-review.png", PNG_BYTES, "image/png")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert len(body["items"]) == 2

    batch_id = body["batch_id"]
    last_body = wait_for_batch(client, batch_id)

    assert last_body["status"] == "completed"
    assert last_body["total_items"] == 2
    assert set(last_body["counts"]).issuperset(
        {"queued", "processing", "pass", "fail", "processing_error"}
    )
    assert all("status" in item for item in last_body["items"])


def test_batch_guard_fails_cleo_lowercase_warning_from_wire_response() -> None:
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
    batch_service = BatchService(
        settings=Settings(provider_mode="local"),
        verification_service=verification_service,
    )
    app.dependency_overrides[get_batch_service] = lambda: batch_service
    client = TestClient(app)
    cleo_path = sample_label_path("fail/cleo_2019-04-17_lowercase_warning.png")

    with open(cleo_path, "rb") as file:
        response = client.post(
            "/api/batches",
            files=[
                (
                    "files",
                    ("cleo_2019-04-17_lowercase_warning.png", file, "image/png"),
                )
            ],
        )

    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    last_body = wait_for_batch(client, batch_id)

    assert last_body["status"] == "completed"
    item = last_body["items"][0]
    assert item["status"] == "fail"
    assert item["result"]["fields"]["government_warning"]["status"] == "fail"
    assert "government warning:" in item["result"]["fields"]["government_warning"]["label_value"]
    assert "GOVERNMENT WARNING:" not in item["result"]["fields"]["government_warning"]["label_value"]
    assert "warning_heading_text" not in item["result"]["fields"]["government_warning"]


def test_batch_guard_keeps_one_failing_warning_in_multi_item_batch() -> None:

    class MultiItemWireFakeProvider:
        async def verify(
            self,
            upload: ValidatedUpload,
            item_id: str,
            application_values: ApplicationValues | None = None,
        ) -> ProviderResult:
            warning = make_raw_warning_field()
            if "cleo" in upload.filename:
                warning = make_raw_warning_field(
                    status="pass",
                    label_value=GOVERNMENT_WARNING_FULL_TEXT,
                    reason="Model incorrectly canonicalized lowercase heading.",
                    warning_heading_text="government warning:",
                    warning_full_text=GOVERNMENT_WARNING_FULL_TEXT.replace(
                        "GOVERNMENT WARNING:", "government warning:"
                    ),
                )
            return parse_chat_completion_response(
                response=make_provider_response(
                    json_body={
                        "message": {
                            "content": json.dumps(
                                make_chat_completion_result_content(
                                    government_warning=warning
                                )
                            )
                        }
                    }
                ),
                model="test-wire-model",
                provider_name="test-wire",
                provider_mode="local",
                started=time.perf_counter(),
                attempted_models=["test-wire-model"],
            )

    verification_service = VerificationService(MultiItemWireFakeProvider())
    batch_service = BatchService(
        settings=Settings(provider_mode="local"),
        verification_service=verification_service,
    )
    app.dependency_overrides[get_batch_service] = lambda: batch_service
    client = TestClient(app)
    cleo_path = sample_label_path("fail/cleo_2019-04-17_lowercase_warning.png")
    pass_path = sample_label_path("pass/3_steves_winery_2017-05-25.png")

    with open(cleo_path, "rb") as cleo_file, open(pass_path, "rb") as pass_file:
        response = client.post(
            "/api/batches",
            files=[
                (
                    "files",
                    ("cleo_2019-04-17_lowercase_warning.png", cleo_file, "image/png"),
                ),
                ("files", ("3_steves_winery_2017-05-25.png", pass_file, "image/png")),
            ],
        )

    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    last_body = wait_for_batch(client, batch_id)

    statuses = {item["filename"]: item["status"] for item in last_body["items"]}
    assert statuses["cleo_2019-04-17_lowercase_warning.png"] == "fail"
    assert statuses["3_steves_winery_2017-05-25.png"] == "pass"


def test_batch_logs_lifecycle_without_payload_contents(caplog) -> None:
    caplog.set_level(logging.INFO, logger="alv.api")
    caplog.set_level(logging.INFO, logger="alv.batch")
    caplog.set_level(logging.INFO, logger="alv.verification")

    class TestProvider:
        async def verify(
            self,
            upload: ValidatedUpload,
            item_id: str,
            application_values: ApplicationValues | None = None,
        ) -> ProviderResult:
            return ProviderResult(
                status=VerificationStatus.pass_status,
                summary="The test provider returned a pass result.",
                fields=make_fields(),
                model=ModelMetadata(
                    provider="test",
                    model="test-provider",
                    provider_mode="local",
                    attempted_models=["test-provider"],
                ),
            )

    test_batch_service = BatchService(
        settings=Settings(provider_mode="local"),
        verification_service=VerificationService(TestProvider()),
    )
    app.dependency_overrides[get_batch_service] = lambda: test_batch_service
    client = TestClient(app)

    response = client.post(
        "/api/batches",
        files=[
            ("files", ("sample-one.png", PNG_BYTES, "image/png")),
            ("files", ("sample-two.png", PNG_BYTES, "image/png")),
        ],
        data={"rows": json.dumps([{"brand_name": "One"}, {"brand_name": "Two"}])},
    )

    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    wait_for_batch(client, batch_id)

    messages = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("alv.")
    )
    assert "Batch upload request received" in messages
    assert "Batch upload validation started: file_count=2 rows_present=True" in messages
    assert f"Batch upload validation accepted: batch_id={batch_id}" in messages
    assert f"Batch queued: batch_id={batch_id}" in messages
    assert f"Batch processing started: batch_id={batch_id}" in messages
    assert f"Batch item processing started: batch_id={batch_id}" in messages
    assert "Review started for" in messages
    assert f"Batch item processing completed: batch_id={batch_id}" in messages
    assert f"Batch completed: batch_id={batch_id}" in messages
    assert "iVBOR" not in messages
    assert "test-png" not in messages
    assert "APPLICATION_VALUES_JSON" not in messages
    assert "Authorization" not in messages
    assert "Bearer" not in messages
    assert "OPENROUTER_API_KEY" not in messages


def test_batch_accepts_aligned_rows() -> None:
    client = make_test_client()

    response = client.post(
        "/api/batches",
        files=[
            ("files", ("coyam.png", PNG_BYTES, "image/png")),
            ("files", ("casamigos.png", PNG_BYTES, "image/png")),
        ],
        data={
            "rows": json.dumps(
                [
                    {"filename": "coyam.png", "brand_name": "Coyam", "beverage_class": "wine"},
                    {"filename": "casamigos.png", "brand_name": "Casamigos", "beverage_class": "spirits"},
                ]
            )
        },
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_batch_rejects_misaligned_rows() -> None:
    client = make_test_client()

    response = client.post(
        "/api/batches",
        files=[("files", ("coyam.png", PNG_BYTES, "image/png"))],
        data={"rows": json.dumps([{"brand_name": "Coyam"}, {"brand_name": "Extra"}])},
    )

    assert response.status_code == 400
