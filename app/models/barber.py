from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.service import ServiceResponse

class BarberBase(BaseModel):
    user_id: Optional[UUID] = None
    full_name: str = Field(..., min_length=2, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    active: bool = Field(default=True)

class BarberCreate(BarberBase):
    pass

class BarberUpdate(BaseModel):
    user_id: Optional[UUID] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    active: Optional[bool] = None

class BarberResponse(BarberBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class BarberWithServicesResponse(BarberResponse):
    services: List[ServiceResponse] = []
