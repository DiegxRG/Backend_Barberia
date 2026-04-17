from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import time, date, datetime
from uuid import UUID

# -- Availability Rule --
class AvailabilityRuleBase(BaseModel):
    day_of_week: int = Field(..., ge=1, le=7, description="ISO DOW: 1=Lunes, 7=Domingo")
    start_time: time
    end_time: time
    slot_interval_minutes: int = Field(default=30, gt=0)
    active: bool = Field(default=True)

class AvailabilityRuleCreate(AvailabilityRuleBase):
    pass

class AvailabilityRuleResponse(AvailabilityRuleBase):
    id: UUID
    barber_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BulkAvailabilityRuleCreate(BaseModel):
    rules: List[AvailabilityRuleCreate]

# -- Break --
class BreakBase(BaseModel):
    day_of_week: int = Field(..., ge=1, le=7)
    start_time: time
    end_time: time
    description: Optional[str] = None
    active: bool = Field(default=True)

class BreakCreate(BreakBase):
    pass

class BreakResponse(BreakBase):
    id: UUID
    barber_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# -- Day Off --
class DayOffBase(BaseModel):
    date: date
    reason: Optional[str] = None

class DayOffCreate(DayOffBase):
    pass

class DayOffResponse(DayOffBase):
    id: UUID
    barber_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# -- Aggregated Responses --
class FullAvailabilityResponse(BaseModel):
    barber_id: UUID
    rules: List[AvailabilityRuleResponse]
    breaks: List[BreakResponse]
