from pydantic import BaseModel, validator

from .db import Base


class VinPostRequest(BaseModel):
    vin: str

    @validator("vin")
    def validate_vin(cls, vin):
        if len(vin) != 17 or not vin.isalnum():
            raise ValueError("VIN must contain 17 alphanumeric characters")
        return vin


class VinPostResponse(BaseModel):
    vin_requested: str
    make: str
    model: str
    model_year: str
    body_class: str
    cached_result: bool


class VinDeleteRequest(BaseModel):
    vin: str

    @validator("vin")
    def validate_vin(cls, vin):
        if not len(vin) != 17 or not vin.isalnum():
            raise ValueError("VIN must contain 17 alphanumeric characters")
        return vin


class VinDeleteResponse(BaseModel):
    vin_requested: str
    delete_success: bool
