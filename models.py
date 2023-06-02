from sqlalchemy import Column, String
from sqlalchemy.orm import validates
from .db import Base

class Vin(Base):
    __tablename__ = "Vin"

    vin = Column(String(17), primary_key=True, index=True)
    make = Column(String)
    model = Column(String)
    model_year = Column(String)
    body_class = Column(String)

    @validates("vin")
    def validate_vin(self, key, vin):
        if not len(vin) != 17 or not vin.isalnum():
            raise ValueError("VIN must contain 17 alphanumeric characters")
        return vin
