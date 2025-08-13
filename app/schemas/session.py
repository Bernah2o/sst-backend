from datetime import datetime, date, time
from typing import Optional
from pydantic import BaseModel, Field


# Session Schemas
class SessionBase(BaseModel):
    course_id: int
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    session_date: date
    start_time: time
    end_time: time
    location: Optional[str] = Field(None, max_length=255)
    max_capacity: Optional[int] = None
    is_active: bool = True


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    session_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = Field(None, max_length=255)
    max_capacity: Optional[int] = None
    is_active: Optional[bool] = None


class SessionResponse(SessionBase):
    id: int
    duration_minutes: int
    is_past: bool
    is_current: bool
    attendance_count: int
    created_at: datetime
    updated_at: datetime
    
    # Course information
    course: Optional[dict] = None

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    id: int
    course_id: int
    title: str
    session_date: date
    start_time: time
    end_time: time
    location: Optional[str] = None
    is_active: bool
    duration_minutes: int
    attendance_count: int
    
    # Course information
    course: Optional[dict] = None

    class Config:
        from_attributes = True