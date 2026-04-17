from datetime import date
from typing import List
from uuid import UUID

from pydantic import BaseModel


class SlotItem(BaseModel):
    start: str
    end: str
    available: bool


class SlotsResponse(BaseModel):
    barber_id: UUID
    service_id: UUID
    date: date
    timezone: str
    slots: List[SlotItem]
