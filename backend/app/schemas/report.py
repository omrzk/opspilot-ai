import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ReportKind = Literal[
    "incident_report",
    "executive_summary",
    "technical_report",
    "postmortem",
    "runbook",
]


class ReportCreate(BaseModel):
    kind: ReportKind
    analysis_id: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None
    title: str = ""
    instructions: str = ""


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    content_md: str
    status: str
    error: str
    analysis_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    created_at: datetime


class IncidentCreate(BaseModel):
    title: str
    description: str = ""
    severity: str = "medium"
    analysis_id: uuid.UUID | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    status: str | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    severity: str
    status: str
    analysis_id: uuid.UUID | None
    created_at: datetime
    resolved_at: datetime | None
