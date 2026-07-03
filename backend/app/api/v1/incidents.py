"""Incident tracking (lightweight, links analyses to reports)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import utcnow
from app.db.session import get_db
from app.models.incident import Incident
from app.models.user import User
from app.schemas.report import IncidentCreate, IncidentOut, IncidentUpdate

router = APIRouter(prefix="/incidents", tags=["incidents"])

VALID_STATUSES = {"open", "investigating", "mitigated", "resolved", "closed"}
VALID_SEVERITIES = {"critical", "high", "medium", "low", "informational"}


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IncidentOut:
    if payload.severity not in VALID_SEVERITIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid severity")
    incident = Incident(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        analysis_id=payload.analysis_id,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return IncidentOut.model_validate(incident)


@router.get("", response_model=list[IncidentOut])
async def list_incidents(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[IncidentOut]:
    rows = (
        await db.execute(
            select(Incident).where(Incident.user_id == user.id).order_by(Incident.created_at.desc())
        )
    ).scalars()
    return [IncidentOut.model_validate(i) for i in rows]


@router.patch("/{incident_id}", response_model=IncidentOut)
async def update_incident(
    incident_id: uuid.UUID,
    payload: IncidentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IncidentOut:
    incident = await db.get(Incident, incident_id)
    if incident is None or incident.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    if payload.severity is not None:
        if payload.severity not in VALID_SEVERITIES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid severity")
        incident.severity = payload.severity
    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid status")
        incident.status = payload.status
        incident.resolved_at = utcnow() if payload.status in ("resolved", "closed") else None
    if payload.title is not None:
        incident.title = payload.title
    if payload.description is not None:
        incident.description = payload.description
    await db.commit()
    await db.refresh(incident)
    return IncidentOut.model_validate(incident)


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(
    incident_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    incident = await db.get(Incident, incident_id)
    if incident is None or incident.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    await db.delete(incident)
    await db.commit()
