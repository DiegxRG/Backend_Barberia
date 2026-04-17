from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class ServiceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    duration_minutes: int = Field(..., gt=0)
    price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    category: str = Field(default="general")
    image_url: Optional[str] = None
    active: bool = Field(default=True)

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    price: Optional[Decimal] = Field(None, ge=0, max_digits=10, decimal_places=2)
    category: Optional[str] = None
    image_url: Optional[str] = None
    active: Optional[bool] = None

class ServiceResponse(ServiceBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
