from typing import Annotated
from pydantic import BaseModel, Field

Portions = Annotated[int, Field(ge=1)]


class ReceiptIn(BaseModel):
    receipt_id: str = Field(min_length=1, max_length=64)
    stall: str = Field(min_length=1, max_length=64)
    total_portions: Portions


class ClaimIn(BaseModel):
    stall: str = Field(min_length=1, max_length=64)
    portions: Portions
