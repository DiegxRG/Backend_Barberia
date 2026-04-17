from datetime import datetime
from typing import Optional, Literal, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


BookingStatus = Literal["pending", "confirmed", "cancelled", "completed", "no_show"]


class BookingCreate(BaseModel):
    barber_id: UUID
    service_id: UUID
    start_at: datetime
    notes: Optional[str] = Field(default=None, max_length=1000)
    idempotency_key: Optional[str] = Field(default=None, max_length=150)
    client_user_id: Optional[UUID] = None

    @field_validator("start_at")
    @classmethod
    def validate_start_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_at debe incluir zona horaria")
        return value


class BookingReschedule(BaseModel):
    start_at: datetime
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("start_at")
    @classmethod
    def validate_start_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_at debe incluir zona horaria")
        return value


class BookingCancel(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class BookingResponse(BaseModel):
    id: UUID
    client_user_id: UUID
    barber_id: UUID
    service_id: UUID
    start_at: datetime
    end_at: datetime
    status: BookingStatus
    notes: Optional[str] = None
    cancel_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    calendar_event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingHistoryResponse(BaseModel):
    id: UUID
    booking_id: UUID
    previous_status: Optional[str] = None
    new_status: str
    changed_by: Optional[UUID] = None
    reason: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
