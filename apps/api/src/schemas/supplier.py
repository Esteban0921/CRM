import uuid

from pydantic import BaseModel, ConfigDict

from models.supplier import SupplierCategory


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    tax_id: str | None
    email: str | None
    category: SupplierCategory
