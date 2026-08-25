import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole
    family_id: uuid.UUID | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: UserRole
    family_id: uuid.UUID | None


class MeResponse(UserRead):
    pass
