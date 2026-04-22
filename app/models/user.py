from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict


class UserListItemResponse(BaseModel):
    id: str
    email: Optional[str] = None
    full_name: str
    role: str
    active: bool
    created_at: datetime
    updated_at: datetime
    linked_barber_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserRoleUpdateRequest(BaseModel):
    role: Literal["cliente", "barbero"]
