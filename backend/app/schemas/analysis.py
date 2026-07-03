import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnalysisCreate(BaseModel):
    upload_id: uuid.UUID
    # Optional operator hint, e.g. "focus on authentication failures"
    instructions: str = ""


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    upload_id: uuid.UUID
    status: str
    model: str
    summary: str
    root_cause: str
    severity: str
    confidence: float
    affected_systems: list
    remediation: list
    scripts: dict
    evidence: list
    error: str
    created_at: datetime
    completed_at: datetime | None
