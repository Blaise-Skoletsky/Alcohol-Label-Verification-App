

from app.services.verification_prompt_service import VerificationPromptService


def test_verification_prompt_accepts_application_values() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Stone's Throw",
            "beverage_class": "wine",
            "class_type_designation": "Wine",
            "alcohol_content": "13.5% ABV",
            "net_contents": "750 mL",
            "name_address": "Example Producer, Napa, CA",
            "country_of_origin": "Domestic",
        }
    )

    assert "\"brand_name\": \"Stone's Throw\"" in prompt.user_instruction
    assert '"beverage_class": "wine"' in prompt.user_instruction
    assert '"class_type_designation": "Wine"' in prompt.user_instruction
    assert '"alcohol_content": "13.5% ABV"' in prompt.user_instruction
    assert "The image is label artwork only" in prompt.system_instruction
    assert "never extract application values from it" in prompt.system_instruction
    assert "application_value='N/A - text entry form'" in prompt.system_instruction


def test_prompt_skips_table_wine_alcohol_content_when_not_required() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Example",
            "beverage_class": "wine",
            "class_type_designation": "Table Wine",
            "alcohol_content": "",
            "net_contents": "750 mL",
            "name_address": "Example Producer, Napa, CA",
            "country_of_origin": "Domestic",
        }
    )

    assert "alcohol_content" not in prompt.requested_fields
    assert "FIELD 4 - alcohol_content" not in prompt.system_instruction
    assert "Requested fields:" in prompt.system_instruction
    assert "alcohol_content" not in prompt.system_instruction.split("Requested fields: ")[1]
    assert prompt.deterministic_fields["alcohol_content"]["status"] == "pass"
    assert "Backend applicability" in prompt.deterministic_fields["alcohol_content"]["reason"]


def test_prompt_allows_specific_wine_designation_for_table_wine_class_type() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "3 Steves Winery",
            "beverage_class": "wine",
            "class_type_designation": "Table Wine",
            "alcohol_content": "",
            "net_contents": "750 mL",
            "name_address": "Bottled By 3 Steves Winery, Livermore, CA",
            "country_of_origin": "Domestic",
        }
    )

    assert "If" in prompt.system_instruction
    assert "application says Table Wine or Light Wine" in prompt.system_instruction
    assert "Chardonnay" in prompt.system_instruction
    assert "no conflicting" in prompt.system_instruction
    assert "class appears" in prompt.system_instruction


def test_prompt_allows_class_type_modifiers_and_obvious_spelling_variants() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Blue Ridge",
            "beverage_class": "wine",
            "class_type_designation": "White grape wine with artificial flavor",
            "alcohol_content": "Alc. 11% by vol.",
            "net_contents": "750 mL",
            "name_address": "Vinted and bottled by Blue Ridge Winery, LLC",
            "country_of_origin": "Domestic",
        }
    )

    assert "Harmless descriptive modifiers" in prompt.system_instruction
    assert "off dry" in prompt.system_instruction
    assert "OCR/label spelling variants" in prompt.system_instruction
    assert "artifical matching artificial" in prompt.system_instruction


def test_prompt_requires_beverage_class_to_match_label_class_family() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "brand_name": "Example",
            "beverage_class": "malt",
            "class_type_designation": "Beer",
            "alcohol_content": "5% by vol.",
            "net_contents": "12 fl. oz.",
            "name_address": "Example Brewery, Portland, OR",
            "country_of_origin": "Domestic",
        }
    )

    assert "Compare both APPLICATION_VALUES_JSON.beverage_class" in prompt.system_instruction
    assert "The broad beverage class must line up first" in prompt.system_instruction
    assert "wine labels cannot pass" in prompt.system_instruction
    assert "malt/beer applications" in prompt.system_instruction
    assert "wine label" in prompt.system_instruction
    assert "Beer/Ale/Malt" in prompt.system_instruction
    assert "fails this field" in prompt.system_instruction


def test_prompt_forbids_net_contents_inference() -> None:
    prompt = VerificationPromptService().build_prompt()

    assert "Do not infer common bottle sizes" in prompt.system_instruction
    assert "barcode" in prompt.system_instruction
    assert "unless the same quantity/unit is visible" in prompt.system_instruction


def test_prompt_requires_word_for_word_government_warning() -> None:
    prompt = VerificationPromptService().build_prompt()

    assert "required federal warning words in order" in prompt.system_instruction
    assert "missing any required word" in prompt.system_instruction
    assert "changed/reordered/paraphrased wording" in prompt.system_instruction
    assert "heading words" in prompt.system_instruction
    assert "GOVERNMENT WARNING are all caps" in prompt.system_instruction
    assert "colon after WARNING" in prompt.system_instruction
    assert "do not fail solely because the colon is missing" in prompt.system_instruction
    assert "sentence case or all" in prompt.system_instruction
    assert "mixed-case heading" in prompt.system_instruction
    assert "return the full visible warning statement when readable" in prompt.system_instruction
    assert "only the heading" in prompt.system_instruction
    assert "non-exact heading" in prompt.system_instruction
    assert "fail the" in prompt.system_instruction


def test_prompt_requires_distilled_spirits_alcohol_content() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "spirits",
            "class_type_designation": "Vodka",
            "alcohol_content": "",
            "country_of_origin": "Domestic",
        }
    )

    assert "alcohol_content" in prompt.requested_fields
    assert "Alcohol content is required or was submitted for comparison." in prompt.system_instruction
    assert "distilled spirits" in prompt.system_instruction


def test_prompt_skips_malt_alcohol_content_without_added_nonbeverage_trigger() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "malt",
            "class_type_designation": "Ale",
            "alcohol_content": "",
            "country_of_origin": "Domestic",
            "malt_added_nonbeverage_alcohol": False,
        }
    )

    assert "alcohol_content" not in prompt.requested_fields
    assert prompt.deterministic_fields["alcohol_content"]["status"] == "pass"


def test_prompt_requires_malt_alcohol_content_with_added_nonbeverage_trigger() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "malt",
            "class_type_designation": "Ale",
            "alcohol_content": "",
            "country_of_origin": "Domestic",
            "malt_added_nonbeverage_alcohol": True,
        }
    )

    assert "alcohol_content" in prompt.requested_fields
    assert "Alcohol content is required" in prompt.system_instruction


def test_prompt_checks_malt_color_additive_only_when_applicable() -> None:
    prompt = VerificationPromptService().build_prompt(
        {
            "beverage_class": "malt",
            "class_type_designation": "Ale",
            "country_of_origin": "Domestic",
            "malt_color_additive_applicable": True,
        }
    )

    assert "color_additive_disclosure" in prompt.requested_fields
    assert "FIELD 8 - color_additive_disclosure" in prompt.system_instruction


def test_prompt_targets_domestic_country_of_origin_check() -> None:
    prompt = VerificationPromptService().build_prompt({"country_of_origin": "Domestic"})

    assert "Application says Domestic" in prompt.system_instruction
    assert "Product of" in prompt.system_instruction
    assert "does not show an imported origin" in prompt.system_instruction
    assert "No imported origin statement visible" in prompt.system_instruction
    assert "do not use N/A" in prompt.system_instruction


def test_prompt_targets_country_name_origin_check() -> None:
    prompt = VerificationPromptService().build_prompt({"country_of_origin": "Chile"})

    assert "Application provides a country name" in prompt.system_instruction
    assert "country conflicts" in prompt.system_instruction
    assert "Application country for this row: Chile" in prompt.system_instruction
