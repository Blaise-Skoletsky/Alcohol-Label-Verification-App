from pydantic import BaseModel


class VerificationError(BaseModel):
    code: str
    message: str
