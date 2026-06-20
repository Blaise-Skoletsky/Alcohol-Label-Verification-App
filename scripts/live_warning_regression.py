"""Live API regression checks for government-warning prompt balance.

This script sends known pass/fail sample labels through the running /api/verify
API. It intentionally uses the real configured provider behind that API, so it
is slow and environment-dependent compared with the unit tests.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "frontend" / "public" / "sample_labels"

CASES = [
    {
        "name": "lowercase government warning prefix",
        "expected_warning_status": "fail",
        "path": SAMPLE_ROOT / "fail" / "cleo_2019-04-17_lowercase_warning.png",
        "fields": {
            "brand_name": "Cleo",
            "beverage_class": "spirits",
            "class_type_designation": "Gin",
            "alcohol_content": "40% Alc/Vol",
            "net_contents": "750 ml",
            "name_address": "Distilled and bottled by Black Market Spirits, Santa Barbara, CA",
            "country_of_origin": "Domestic",
        },
    },
    {
        "name": "mixed-case government warning prefix",
        "expected_warning_status": "fail",
        "path": SAMPLE_ROOT / "fail" / "gekkeikan_2014-09-11_mixedcase_warning.png",
        "fields": {
            "brand_name": "Gekkeikan Gold",
            "beverage_class": "wine",
            "class_type_designation": "Junmai Sake",
            "alcohol_content": "16.5% Alc./Vol.",
            "net_contents": "720 ml",
            "name_address": (
                "Produced by Gekkeikan Sake Company, Ltd.; Imported by Sidney Frank "
                "Importing Co., Inc., New Rochelle, NY"
            ),
            "country_of_origin": "Japan",
        },
    },
    {
        "name": "valid imported honey liqueur warning",
        "expected_warning_status": "pass",
        "path": SAMPLE_ROOT / "pass" / "barenjager_2011-03-09_11038001000727.png",
        "fields": {
            "brand_name": "Barenjager",
            "beverage_class": "spirits",
            "class_type_designation": "Honey Liqueur",
            "alcohol_content": "35% Alc. by Vol.",
            "net_contents": "50 ml",
            "name_address": (
                "Imported by Sidney Frank Importing Co., Inc., New Rochelle, NY; "
                "produced and bottled in Germany"
            ),
            "country_of_origin": "Germany",
        },
    },
    {
        "name": "valid domestic Cabernet Sauvignon warning",
        "expected_warning_status": "pass",
        "path": SAMPLE_ROOT / "pass" / "3_steves_winery_2017-05-25.png",
        "fields": {
            "brand_name": "3 Steves Reserve",
            "beverage_class": "wine",
            "class_type_designation": "Cabernet Sauvignon",
            "alcohol_content": "Alcohol: 14.6% by volume",
            "net_contents": "750 ml",
            "name_address": (
                "Grown, Produced and Bottled by 3 Steves Winery, "
                "Livermore Valley, California"
            ),
            "country_of_origin": "Domestic",
        },
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://localhost:7001",
        help="Running ALV API base URL. Default: http://localhost:7001",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Per-request timeout in seconds. Default: 180",
    )
    args = parser.parse_args()

    failures = []
    for case in CASES:
        result = verify_case(args.base_url, args.timeout, case)
        warning = result.get("fields", {}).get("government_warning", {})
        warning_status = warning.get("status")
        status = result.get("status")
        label_value = warning.get("label_value", "")
        reason = warning.get("reason", "")

        print(f"\n{case['path'].name}")
        print(f"  overall status: {status}")
        print(f"  government_warning status: {warning_status}")
        print(f"  government_warning label_value: {label_value}")
        print(f"  government_warning reason: {reason}")

        expected_status = case["expected_warning_status"]
        if warning_status != expected_status:
            failures.append(
                f"{case['path'].name}: expected government_warning={expected_status}, "
                f"got {warning_status}"
            )

    if failures:
        print("\nFAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nPASS: live government-warning regressions matched expected outcomes.")
    return 0


def verify_case(base_url: str, timeout: float, case: dict) -> dict:
    path = Path(case["path"])
    if not path.exists():
        raise FileNotFoundError(path)

    body, content_type = build_multipart(path, case["fields"])
    request = Request(
        urljoin(base_url.rstrip("/") + "/", "api/verify"),
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path.name}: API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{path.name}: could not reach API at {base_url}: {exc}") from exc


def build_multipart(path: Path, fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----alv-live-warning-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("ascii"),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


if __name__ == "__main__":
    sys.exit(main())
