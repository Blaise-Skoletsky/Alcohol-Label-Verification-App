import json
import time


from app.models.verification import (
    ModelMetadata,
    VerificationStatus,
)
from app.providers.base import ProviderResult
from app.providers.chat_completion_parser import (
    parse_chat_completion_response,
)
from app.services.result_guard_service import (
    GOVERNMENT_WARNING_FULL_TEXT,
    ResultGuardService,
)
from helpers import (
    make_chat_completion_result_content,
    make_field,
    make_fields,
    make_provider_response,
    make_raw_warning_field,
    make_warning_field,
)


def test_result_guard_fails_non_abv_text_for_alcohol_content() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                alcohol_content=make_field(
                    application_value="13",
                    label_value="DRY RED TABLE WINE",
                    reason="Model incorrectly accepted class text.",
                )
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: alcohol content."
    assert result.fields.alcohol_content.status == "fail"
    assert "alcohol-content" in result.fields.alcohol_content.reason


def test_result_guard_fails_passing_class_type_when_beverage_class_conflicts() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "class_type_designation": make_field(
                        application_value="malt / Beer",
                        label_value="wine / Cabernet Sauvignon",
                        reason="Model incorrectly accepted a class mismatch.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: class/type designation."
    assert result.fields.class_type_designation.status == "fail"
    assert "beverage class" in result.fields.class_type_designation.reason


def test_result_guard_passes_brand_when_submitted_brand_is_in_name_address() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.fail,
            summary="Model failed the brand.",
            fields=make_fields(
                field_updates={
                    "brand_name": make_field(
                        status="fail",
                        application_value="3 Steves Winery",
                        label_value="Stanford",
                        reason="Model incorrectly treated story copy as the brand.",
                    ),
                    "name_address": make_field(
                        application_value=(
                            "Grown, Produced and Bottled by 3 Steves Winery, "
                            "Livermore Valley, California"
                        ),
                        label_value=(
                            "Grown, Produced and Bottled by 3 Steves Winery, "
                            "Livermore Valley, California"
                        ),
                        reason="The responsibility statement is visible on the label.",
                    ),
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.brand_name.status == "pass"
    assert result.fields.brand_name.label_value == "3 Steves Winery"
    assert "Backend guard" in result.fields.brand_name.reason


def test_result_guard_keeps_brand_fail_when_name_address_has_different_brand() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.fail,
            summary="Model failed the brand.",
            fields=make_fields(
                field_updates={
                    "brand_name": make_field(
                        status="fail",
                        application_value="Duck Creek Cellars",
                        label_value="Duck Walk Vineyards",
                        reason="The visible brand does not match the application.",
                    ),
                    "name_address": make_field(
                        application_value="Produced and bottled by Duck Walk Vineyards",
                        label_value="Produced and bottled by Duck Walk Vineyards",
                        reason="The responsibility statement is visible on the label.",
                    ),
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: brand name."
    assert result.fields.brand_name.status == "fail"
    assert result.fields.brand_name.label_value == "Duck Walk Vineyards"


def test_result_guard_passes_table_wine_alcohol_content_exception() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.fail,
            summary="Model failed the field.",
            fields=make_fields(
                alcohol_content=make_field(
                    status="fail",
                    application_value="Not required for table wine designation",
                    label_value="Not required for table wine designation",
                    reason="Alcohol content could not be confidently extracted as an alcohol-content value.",
                )
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.alcohol_content.status == "pass"
    assert result.fields.alcohol_content.reason == (
        "Alcohol content is not required for this table/light wine designation."
    )


def test_result_guard_passes_optional_malt_omission_without_trigger() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model passed optional malt omission.",
            fields=make_fields(
                alcohol_content=make_field(
                    application_value="Not required for malt beverage",
                    label_value="Not required for malt beverage",
                    reason=(
                        "Malt beverage alcohol content is federally optional; "
                        "no added nonbeverage alcohol trigger is visible."
                    ),
                )
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.alcohol_content.status == "pass"


def test_result_guard_treats_decimal_comma_as_matching_abv() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.fail,
            summary="Model failed the field.",
            fields=make_fields(
                alcohol_content=make_field(
                    status="fail",
                    application_value="Alc. 14.5% by vol.",
                    label_value="ALC. 14,5% BY VOL.",
                    reason="Application alcohol content and label alcohol content do not match exactly.",
                )
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.alcohol_content.status == "pass"


def test_result_guard_fails_mixed_case_government_warning_prefix() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_warning_field(
                        application_value="Required federal government warning",
                        label_value=GOVERNMENT_WARNING_FULL_TEXT.replace(
                            "GOVERNMENT WARNING:", "Government Warning:"
                        ),
                        warning_heading_text="Government Warning:",
                        warning_full_text=GOVERNMENT_WARNING_FULL_TEXT.replace(
                            "GOVERNMENT WARNING:", "Government Warning:"
                        ),
                        reason="Model incorrectly accepted title-case prefix.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: government warning."
    assert result.fields.government_warning.status == "fail"
    assert "heading words 'GOVERNMENT WARNING' are visible in all caps" in (
        result.fields.government_warning.reason
    )


def test_result_guard_fails_lowercase_government_warning_heading_extraction() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_warning_field(
                        application_value="Required federal government warning",
                        label_value=GOVERNMENT_WARNING_FULL_TEXT,
                        warning_heading_text="government warning:",
                        warning_full_text=GOVERNMENT_WARNING_FULL_TEXT.replace(
                            "GOVERNMENT WARNING:", "government warning:"
                        ),
                        reason="Model incorrectly accepted lowercase heading.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.fields.government_warning.status == "fail"
    assert "government warning:" in result.fields.government_warning.label_value
    assert "GOVERNMENT WARNING:" not in result.fields.government_warning.label_value
    assert "heading words 'GOVERNMENT WARNING' are visible in all caps" in (
        result.fields.government_warning.reason
    )


def test_result_guard_fails_missing_government_warning_extraction_fields() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_field(
                        application_value="Required federal government warning",
                        label_value=GOVERNMENT_WARNING_FULL_TEXT,
                        reason="Model omitted internal extraction fields.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.fields.government_warning.status == "fail"
    assert "required warning text extraction fields" in result.fields.government_warning.reason


def test_result_guard_fails_malformed_government_warning_boolean_extraction() -> None:
    parsed = parse_chat_completion_response(
        response=make_provider_response(
            json_body={
                "message": {
                    "content": json.dumps(
                        make_chat_completion_result_content(
                            government_warning=make_raw_warning_field(
                                warning_block_visible="true"
                            )
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

    result = ResultGuardService().enforce(parsed)

    assert result.status == VerificationStatus.fail
    assert result.fields.government_warning.status == "fail"
    assert "required warning text extraction fields" in result.fields.government_warning.reason


def test_result_guard_passes_valid_warning_extraction_even_if_model_field_failed() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.fail,
            summary="Model failed the field.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_warning_field(
                        status="fail",
                        reason="Model was uncertain despite valid extracted text.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.government_warning.status == "pass"


def test_result_guard_fails_partial_government_warning_text() -> None:
    partial_warning = (
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should "
        "not drink alcoholic beverages during pregnancy. (2) Consumption of alcoholic "
        "beverages impairs your ability to drive a car or operate machinery."
    )
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_warning_field(
                        application_value="Required federal government warning",
                        label_value=partial_warning,
                        warning_body_text=partial_warning.split(":", 1)[1].strip(),
                        warning_full_text=partial_warning,
                        reason="Model incorrectly accepted partial warning.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: government warning."
    assert result.fields.government_warning.status == "fail"
    assert "because" in result.fields.government_warning.reason


def test_result_guard_allows_warning_spacing_ocr_variants() -> None:
    compact_warning = (
        "GOVERNMENT WARNING (1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD "
        "NOT DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK "
        "OF BIRTH DEFECTS.(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR "
        "ABILITY TO DRIVE A CAR OR OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS."
    )
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_warning_field(
                        application_value="Required federal government warning",
                        label_value=compact_warning,
                        warning_heading_text="GOVERNMENT WARNING",
                        warning_body_text=compact_warning.replace("GOVERNMENT WARNING", "", 1).strip(),
                        warning_full_text=compact_warning,
                        reason="Warning text is present.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.government_warning.status == "pass"


def test_result_guard_reports_first_warning_word_mismatch() -> None:
    altered_warning = GOVERNMENT_WARNING_FULL_TEXT.replace("Surgeon", "Attorney")
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "government_warning": make_warning_field(
                        application_value="Required federal government warning",
                        label_value=altered_warning,
                        warning_body_text=altered_warning.split(":", 1)[1].strip(),
                        warning_full_text=altered_warning,
                        reason="Model incorrectly accepted changed warning.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert "surgeon" in result.fields.government_warning.reason
    assert "attorney" in result.fields.government_warning.reason


def test_result_guard_allows_domestic_origin_without_origin_statement() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "country_of_origin": make_field(
                        application_value="Domestic",
                        label_value="N/A",
                        reason="No imported origin statement is visible on this domestic label.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.country_of_origin.status == "pass"
    assert result.fields.country_of_origin.label_value == "No imported origin statement visible"


def test_result_guard_allows_artifact_legibility_application_na() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "artifact_legibility": make_field(
                        application_value="N/A - text entry form",
                        label_value="Label artwork readable",
                        reason="Label artwork is readable.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.pass_status
    assert result.fields.artifact_legibility.status == "pass"


def test_result_guard_fails_artifact_legibility_when_label_unreadable() -> None:
    result = ResultGuardService().enforce(
        ProviderResult(
            status=VerificationStatus.pass_status,
            summary="Model claimed everything passed.",
            fields=make_fields(
                field_updates={
                    "artifact_legibility": make_field(
                        application_value="N/A - text entry form",
                        label_value="Unreadable",
                        reason="Model incorrectly accepted unreadable label artwork.",
                    )
                }
            ),
            model=ModelMetadata(
                provider="test",
                model="test-double",
                provider_mode="local",
            ),
        )
    )

    assert result.status == VerificationStatus.fail
    assert result.summary == "Required checks failed: artifact legibility."
    assert result.fields.artifact_legibility.status == "fail"
    assert "label image is readable" in result.fields.artifact_legibility.reason
