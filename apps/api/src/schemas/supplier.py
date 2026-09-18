import uuid

from pydantic import BaseModel, ConfigDict, Field

from models.supplier import SupplierCategory


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1)
    tax_id: str | None = None
    email: str | None = None
    category: SupplierCategory = SupplierCategory.OTHER


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    tax_id: str | None = None
    email: str | None = None
    category: SupplierCategory | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    tax_id: str | None
    email: str | None
    category: SupplierCategory
