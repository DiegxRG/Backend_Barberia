from datetime import datetime

from pydantic import BaseModel


class CalendarStatusResponse(BaseModel):
    connected: bool
    calendar_id: str | None = None
    token_expires_at: datetime | None = None


class CalendarCallbackResponse(BaseModel):
    connected: bool
    message: str
    role: str | None = None


class CalendarConnectUrlResponse(BaseModel):
    auth_url: str
