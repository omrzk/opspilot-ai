import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    source_type: str
    status: str
    record_count: int
    error: str
    created_at: datetime


class LogEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime | None
    source: str
    host: str
    severity: str
    event_id: str
    message: str
    raw: dict
