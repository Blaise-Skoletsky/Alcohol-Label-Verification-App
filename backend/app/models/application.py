from typing import Literal

from pydantic import BaseModel

BeverageClass = Literal["spirits", "wine", "malt"]


class ApplicationValues(BaseModel):
    """Reviewer-entered application data compared against the label image.

    These are the human-entered values for a single label. The government
    warning and artifact legibility are detected from the image and never
    appear here.
    """

    brand_name: str | None = None
    beverage_class: BeverageClass | None = None
    class_type_designation: str | None = None
    alcohol_content: str | None = None
    net_contents: str | None = None
    name_address: str | None = None
    country_of_origin: str | None = None

    def to_prompt_mapping(self) -> dict[str, str | None]:
        """Values keyed exactly as the verification prompt expects them.

        ``beverage_class`` is intentionally omitted: the prompt reasons about
        the beverage class from ``class_type_designation`` and the label, and
        ``VerificationPromptService`` only reads the six comparison fields.
        """

        return {
            "brand_name": self.brand_name,
            "class_type_designation": self.class_type_designation,
            "alcohol_content": self.alcohol_content,
            "net_contents": self.net_contents,
            "name_address": self.name_address,
            "country_of_origin": self.country_of_origin,
        }
