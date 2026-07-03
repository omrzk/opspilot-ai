"""AI-generated reports: incident reports, exec summaries, postmortems, runbooks."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.incident import Incident
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportCreate, ReportOut
from app.workers.tasks import generate_report_task

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    payload: ReportCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    if payload.analysis_id is None and payload.incident_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Provide analysis_id and/or incident_id as report context",
        )
    if payload.analysis_id is not None:
        analysis = await db.get(Analysis, payload.analysis_id)
        if analysis is None or analysis.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
        if analysis.status != "completed":
            raise HTTPException(status.HTTP_409_CONFLICT, "Analysis is not completed yet")
    if payload.incident_id is not None:
        incident = await db.get(Incident, payload.incident_id)
        if incident is None or incident.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")

    report = Report(
        user_id=user.id,
        kind=payload.kind,
        title=payload.title,
        analysis_id=payload.analysis_id,
        incident_id=payload.incident_id,
        status="queued",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    generate_report_task.delay(str(report.id), payload.instructions)
    return ReportOut.model_validate(report)


@router.get("", response_model=list[ReportOut])
async def list_reports(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ReportOut]:
    rows = (
        await db.execute(
            select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc())
        )
    ).scalars()
    return [ReportOut.model_validate(r) for r in rows]


async def _owned_report(db: AsyncSession, user: User, report_id: uuid.UUID) -> Report:
    report = await db.get(Report, report_id)
    if report is None or report.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    return ReportOut.model_validate(await _owned_report(db, user, report_id))


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    report = await _owned_report(db, user, report_id)
    if report.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Report is not completed yet")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in report.title)[:80]
    return Response(
        content=report.content_md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name or report.kind}.md"'
        },
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    report = await _owned_report(db, user, report_id)
    await db.delete(report)
    await db.commit()
